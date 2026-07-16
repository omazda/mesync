#!/usr/bin/env python3
"""run_app.py — единый процесс: оба бота (MAX + Telegram) + control-API mini-app.

Запускает в одном event loop:
- Long Polling бота MAX с маршрутизацией по правилам (RuleDispatcher);
- Long Polling бота Telegram с маршрутизацией по правилам и альбомам;
- HTTP control-API (FastAPI/uvicorn) для mini-app;
с ОБЩИМ ControlStore — поэтому коды привязки из mini-app сразу видны ботам,
а изменения правил мгновенно влияют на синхронизацию.

Это all-in-one режим (заменяет раздельные run_stage1.py/run_max.py, когда нужна
маршрутизация по правилам). Боты работают в режиме polling; для webhook-режима
используйте отдельные сервисы и общий каталог данных.

Запуск:  .venv/bin/python run_app.py
Токены — из .env (TELEGRAM_BOT_TOKEN, MAX_BOT_TOKEN).
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import signal
import sys
from pathlib import Path

# src/ на путь импорта
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import uvicorn  # noqa: E402

from control import config as cc  # noqa: E402
from control.api import (  # noqa: E402
    create_app, set_account_avatar_fetcher, set_activation, set_avatar_fetcher, set_broadcaster,
    set_chat_info_provider, set_chat_leaver, set_billing, set_health, set_notifier, set_reports,
    set_restart_handler, set_service_log, set_settings, set_source_notifier,
    set_source_unbinder, set_yandex_market,
)
from control.broadcasts import Broadcaster  # noqa: E402
from control.health import BotHealth  # noqa: E402
from control.integration import (  # noqa: E402
    RuleDispatcher, make_account_avatar_fetcher, make_avatar_fetcher, make_chat_info_provider,
    make_chat_leaver, make_external_claim_cb, make_extra_codes_provider, make_notifier,
    make_source_notifier, make_source_title_provider, make_source_unbinder,
)
from control.reports import HIDDEN_VIOLATION_TEXT, Reports  # noqa: E402
from control.registration_reminders import RegistrationReminderWorker  # noqa: E402
from control.sent_index import SentIndex  # noqa: E402
from control.settings import Settings  # noqa: E402
from control.source_ids import parse_chat_key, topic_title  # noqa: E402
from control.store import ControlStore  # noqa: E402

log = logging.getLogger("run_app")

_TG_HIDDEN_MEDIA_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def _run(store: ControlStore) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    restart_handle: asyncio.TimerHandle | None = None

    def _request_restart() -> None:
        nonlocal restart_handle
        if restart_handle is None:
            # Даём HTTP-ответу restore уйти в браузер, затем запускаем обычный graceful stop.
            restart_handle = loop.call_later(1.0, stop.set)

    # Реестр сообщений, созданных ботом (персистентный) — чтобы бот не синхронизировал свои же
    # сообщения (петля двунаправленного правила; свой пост канала без sender_id; пересылка).
    sent_index = SentIndex(cc.SENT_INDEX_FILE, ttl_seconds=cc.SENT_INDEX_TTL,
                           max_entries=cc.SENT_INDEX_MAX)
    sent_index.load()
    from control.message_map import MessageMap
    message_map = MessageMap(cc.MESSAGE_MAP_FILE, ttl_seconds=cc.MESSAGE_MAP_TTL,
                             max_entries=cc.MESSAGE_MAP_MAX)
    message_map.load()
    # Runtime-настройки админ-панели (settings-store поверх дефолтов config).
    settings = Settings(store)
    set_settings(settings)
    # Живость ботов для ops-обзора (in-memory; поллеры пишут через channel(...)).
    bot_health = BotHealth()
    set_health(bot_health)

    # --- клиенты ботов ---
    from max_sync import config as mxc
    from max_sync.client import MaxClient
    from max_sync.logship import ChatRegistry as MaxRegistry
    from max_sync.ownership import OwnershipManager as MaxOwnership
    from max_sync.storage import Storage as MaxStorage
    from max_sync.updates import Stage1Poller as MaxPoller
    from telegram_sync import config as tgc
    from telegram_sync.client import TelegramClient, UploadFile
    from telegram_sync.logship import ChatRegistry as TgRegistry
    from telegram_sync.ownership import OwnershipManager as TgOwnership
    from telegram_sync.storage import Storage as TgStorage
    from telegram_sync.updates import Stage1Poller as TgPoller

    set_restart_handler(_request_restart)
    async with contextlib.AsyncExitStack() as stack:
        stack.callback(set_restart_handler, None)
        max_client = tg_client = None
        max_bot_id = tg_bot_id = None
        max_bot_username = tg_bot_username = None
        if mxc.BOT_TOKEN:
            max_client = await stack.enter_async_context(MaxClient(mxc.BOT_TOKEN, mxc.API_BASE))
            try:
                me = await max_client.get_me(); max_bot_id = me.get("user_id")
                max_bot_username = me.get("username")
                log.info("MAX бот @%s (id=%s)", max_bot_username, max_bot_id)
            except Exception as exc:  # noqa: BLE001
                log.error("MAX get_me не удался: %s", exc)
        else:
            log.warning("MAX_BOT_TOKEN не задан — бот MAX не запущен")

        if tgc.BOT_TOKEN:
            tg_client = await stack.enter_async_context(TelegramClient(tgc.BOT_TOKEN, tgc.API_BASE))
            try:
                me = await tg_client.get_me(); tg_bot_id = me.get("id")
                tg_bot_username = me.get("username")
                log.info("Telegram бот @%s (id=%s)", tg_bot_username, tg_bot_id)
            except Exception as exc:  # noqa: BLE001
                log.error("Telegram get_me не удался: %s", exc)
        else:
            log.warning("TELEGRAM_BOT_TOKEN не задан — бот Telegram не запущен")

        # --- сервисный лог-канал (отчёты об ошибках разработчикам, канал «Info - MeSync») ---
        from control.service_log import ServiceLog
        service_log = ServiceLog(tg_client, cc.SERVICE_LOG_CHAT_ID,
                                 max_per_minute=cc.SERVICE_LOG_MAX_PER_MINUTE)
        if service_log.enabled:
            log.info("Сервисный лог-канал: chat_id=%s", cc.SERVICE_LOG_CHAT_ID)
        else:
            log.info("Сервисный лог-канал выключен (MESYNC_SERVICE_LOG_CHAT_ID не задан)")

        # --- диспетчер правил + хуки api ---
        dispatcher = RuleDispatcher(store, max_client=max_client, tg_client=tg_client,
                                    max_bot_id=max_bot_id, tg_bot_id=tg_bot_id,
                                    sent_index=sent_index, message_map=message_map,
                                    settings=settings)
        dispatcher.service_log = service_log
        set_service_log(service_log)
        # Закрыть httpx-пул ИИ-модерации на shutdown (аналогично yk_client), если он есть.
        if getattr(dispatcher, "_moderation", None) is not None:
            stack.push_async_callback(dispatcher._moderation.aclose)
        # Наблюдатели за отправкой: запоминаем id каждого отправленного ботом сообщения,
        # чтобы не реагировать на него, если оно вернётся (эхо/пересылка пользователем).
        if tg_client is not None:
            tg_client.on_sent = dispatcher.note_tg_sent
        if max_client is not None:
            max_client.on_sent = dispatcher.note_max_sent
        notifier_fn = make_notifier(max_client, tg_client)
        set_notifier(notifier_fn)
        set_chat_leaver(make_chat_leaver(max_client, tg_client))
        # Лаконичные «Источник … привязан/отвязан» + «Скрыть» в чат с ботом.
        source_notifier = make_source_notifier(max_client, tg_client)
        set_source_notifier(source_notifier)
        # Аватары источников (фото чата/канала) для списка в mini-app.
        set_avatar_fetcher(make_avatar_fetcher(max_client, tg_client))
        # Аватары владельцев аккаунтов для админ-панели.
        set_account_avatar_fetcher(make_account_avatar_fetcher(max_client, tg_client))
        # Авто-подтягивание свежих названий чатов/каналов в список источников.
        set_chat_info_provider(make_chat_info_provider(max_client, tg_client))

        tasks: list[asyncio.Task] = []
        max_own = tg_own = None

        async def _on_source_removed(messenger: str, chat_id, title=None):
            cleanup = await store.delete_source_references(messenger, chat_id)
            removed_rules = cleanup.get("removed_rules") or []
            removed_sources = cleanup.get("removed_sources") or {}
            if removed_rules or removed_sources:
                log.info("Источник удалён из-за удаления бота: %s:%s («%s»), правил=%d, привязок=%d",
                         messenger, chat_id, title or chat_id, len(removed_rules),
                         sum(len(v) for v in removed_sources.values()))

        # --- приветствие в личке с ботом ---
        # На ЛЮБОЕ сообщение пользователя в диалоге с ботом (кроме /claim) отвечаем
        # приветствием с кнопками «Открыть приложение», «Условия и политика
        # конфиденциальности» и быстрыми ссылками на второго бота/поддержку. Для MAX
        # `bot_started` дополнительно сохраняет lead, чтобы позже напомнить о регистрации.
        # Кнопки сверены с локальной документацией:
        #   Telegram — InlineKeyboardButton.web_app (docs/telegram 04-api-reference:
        #     «Available in private chats only» — мы шлём только в личку) + url-кнопки;
        #   MAX — inline_keyboard c link/callback-кнопками (docs/max docs-api «Типы кнопок»);
        #     мини-приложение открывается документированным диплинком
        #     https://max.ru/<botName>?startapp (docs/max help/deeplinks).
        WELCOME_TEXT = (
            f"👋 Привет! Я {cc.BOT_NAME} — синхронизирую сообщения и посты между MAX и Telegram.\n\n"
            "Добавьте меня в свои чаты и каналы, создайте правило в приложении — и всё "
            "будет переноситься автоматически: с форматированием и медиа, чистой копией "
            "без пометки «переслано».\n\nУправление — в мини-приложении:")
        BTN_APP = "🚀 Открыть приложение"
        BTN_TERMS = "📄 Условия и политика конфиденциальности"
        BTN_SUPPORT = "Поддержка"
        BTN_BOT_MAX = "Бот в MAX"
        BTN_BOT_TG = "Бот в ТГ"

        def _bot_link(messenger: str, live_username: str | None = None) -> str:
            configured = cc.BOT_URLS.get(messenger, "")
            if configured:
                return configured
            username = (live_username or "").lstrip("@")
            if messenger == "tg":
                return f"https://t.me/{username}" if username else ""
            if messenger == "max":
                return f"https://max.ru/{username}" if username else ""
            return ""

        def _max_app_url() -> str:
            bot_url = _bot_link("max", max_bot_username)
            if not bot_url:
                return cc.APP_URL
            separator = "&" if "?" in bot_url else "?"
            return f"{bot_url}{separator}startapp"

        async def _tg_welcome(norm):
            chat_id = (norm.get("chat") or {}).get("id")
            if chat_id is None or tg_client is None:
                return
            rows = [
                [{"text": BTN_APP, "web_app": {"url": cc.APP_URL}}],
                [{"text": BTN_TERMS, "url": cc.TERMS_URL}],
            ]
            extra = []
            max_url = _bot_link("max", max_bot_username)
            if max_url:
                extra.append({"text": BTN_BOT_MAX, "url": max_url})
            if cc.SUPPORT_TG_URL:
                extra.append({"text": BTN_SUPPORT, "url": cc.SUPPORT_TG_URL})
            if extra:
                rows.append(extra)
            kb = {"inline_keyboard": rows}
            await tg_client.send_message(chat_id, WELCOME_TEXT, parse_mode="HTML",
                                         disable_web_page_preview=True, reply_markup=kb)

        async def _max_welcome(norm):
            user_id = norm.get("sender_id")
            if user_id is None or max_client is None:
                return
            payload = norm.get("start_payload")
            if payload:
                await store.upsert_registration_lead(
                    "max", user_id, chat_id=norm.get("chat_id") or user_id,
                    payload=payload, user=norm.get("sender") or {}, stage="started")
            app_url = _max_app_url()
            buttons = [
                [{"type": "link", "text": BTN_APP, "url": app_url}],
                [{"type": "link", "text": BTN_TERMS, "url": cc.TERMS_URL}],
            ]
            extra = []
            tg_url = _bot_link("tg", tg_bot_username)
            if tg_url:
                extra.append({"type": "link", "text": BTN_BOT_TG, "url": tg_url})
            if cc.SUPPORT_TG_URL:
                extra.append({"type": "link", "text": BTN_SUPPORT, "url": cc.SUPPORT_TG_URL})
            if extra:
                buttons.append(extra)
            await max_client.send_message(
                user_id=user_id, text=WELCOME_TEXT,
                fmt="html", disable_link_preview=True,
                attachments=[{"type": "inline_keyboard", "payload": {"buttons": buttons}}])

        async def _send_max_registration_reminder(lead: dict[str, object], reminder_index: int):
            if max_client is None:
                return None
            user_id = lead.get("user_id")
            if user_id is None:
                return None
            if reminder_index <= 0:
                text = (f"Вы открывали {cc.BOT_NAME}, но регистрация ещё не завершена.\n\n"
                        "Нажмите «Открыть приложение», чтобы подключить синхронизацию MAX и Telegram.")
            else:
                text = (f"Напоминаю про {cc.BOT_NAME}: завершите регистрацию, чтобы связать "
                        "MAX и Telegram и настроить синхронизацию.")
            buttons = [
                [{"type": "link", "text": BTN_APP, "url": _max_app_url()}],
            ]
            extra = []
            tg_url = _bot_link("tg", tg_bot_username)
            if tg_url:
                extra.append({"type": "link", "text": BTN_BOT_TG, "url": tg_url})
            if cc.SUPPORT_TG_URL:
                extra.append({"type": "link", "text": BTN_SUPPORT, "url": cc.SUPPORT_TG_URL})
            if extra:
                buttons.append(extra)
            buttons.append([{"type": "callback", "text": "Скрыть", "payload": "hide_msg"}])
            return await max_client.send_message(
                user_id=user_id, text=text, disable_link_preview=True,
                attachments=[{"type": "inline_keyboard", "payload": {"buttons": buttons}}])

        # --- бот MAX ---
        if max_client is not None:
            max_storage = MaxStorage(mxc.RAW_UPDATES_FILE, mxc.CONTENT_FILE, mxc.MARKER_FILE, mxc.MEDIA_DIR)
            max_registry = MaxRegistry(mxc.KNOWN_CHATS_FILE)
            max_own = MaxOwnership(max_client, mxc.OWNERSHIP_FILE, bot_id=max_bot_id,
                                   raw_updates_file=mxc.RAW_UPDATES_FILE,
                                   extra_codes_provider=make_extra_codes_provider(store, "max"),
                                   on_external_claim=make_external_claim_cb(store, "max", source_notifier),
                                   on_removed=lambda chat_id, title=None:
                                       _on_source_removed("max", chat_id, title))
            await stack.enter_async_context(max_own)
            bot_health.mark_started("max", bot_id=max_bot_id, username=max_bot_username,
                                    poll_timeout=mxc.LONG_POLL_TIMEOUT)
            max_poller = MaxPoller(max_client, max_storage, chat_registry=max_registry,
                                   ownership=max_own, update_types=mxc.UPDATE_TYPES,
                                   timeout=mxc.LONG_POLL_TIMEOUT, limit=mxc.GET_UPDATES_LIMIT,
                                   download_media=mxc.DOWNLOAD_MEDIA, max_download_bytes=mxc.MAX_DOWNLOAD_BYTES,
                                   bot_id=max_bot_id, rule_router=dispatcher.on_max_message,
                                   rule_edit_router=dispatcher.on_max_edit,
                                   warn_hide_cb=dispatcher.note_chat_warn_hidden,
                                   dm_welcome=_max_welcome,
                                   health=bot_health.channel("max"))
            tasks.append(asyncio.create_task(max_poller.run(), name="max-poller"))

        # --- бот Telegram ---
        if tg_client is not None:
            async def _confirm_tg_contact(user_id, phone):
                # UpdateRouter уже проверил, что это private self-contact. Store атомарно
                # заполнит legacy-аккаунт либо объединит дубль по подтверждённому номеру.
                account = await store.confirm_identity_phone("tg", user_id, phone)
                log.info("Telegram self-contact подтверждён для account=%s", account["id"])

            tg_storage = TgStorage(tgc.RAW_UPDATES_FILE, tgc.CONTENT_FILE, tgc.OFFSET_FILE, tgc.MEDIA_DIR)
            tg_registry = TgRegistry(tgc.KNOWN_CHATS_FILE)
            tg_own = TgOwnership(tg_client, tgc.OWNERSHIP_FILE, bot_id=tg_bot_id,
                                 raw_updates_file=tgc.RAW_UPDATES_FILE,
                                 extra_codes_provider=make_extra_codes_provider(store, "tg"),
                                 on_external_claim=make_external_claim_cb(store, "tg", source_notifier),
                                 on_rights_change=dispatcher.on_tg_rights_change,
                                 on_removed=lambda chat_id, title=None:
                                     _on_source_removed("tg", chat_id, title))
            await stack.enter_async_context(tg_own)
            bot_health.mark_started("tg", bot_id=tg_bot_id, username=tg_bot_username,
                                    poll_timeout=tgc.LONG_POLL_TIMEOUT)
            tg_poller = TgPoller(tg_client, tg_storage, allowed_updates=tgc.ALLOWED_UPDATES,
                                 timeout=tgc.LONG_POLL_TIMEOUT, limit=tgc.GET_UPDATES_LIMIT,
                                 download_media=tgc.DOWNLOAD_MEDIA, max_download_bytes=tgc.MAX_DOWNLOAD_BYTES,
                                 media_debounce=tgc.MEDIA_GROUP_DEBOUNCE, chat_registry=tg_registry,
                                 ownership=tg_own, rule_router=dispatcher.on_tg_message,
                                 rule_album=dispatcher.on_tg_album,
                                 rule_edit_router=dispatcher.on_tg_edit,
                                 warn_hide_cb=dispatcher.note_chat_warn_hidden,
                                 dm_welcome=_tg_welcome, contact_cb=_confirm_tg_contact,
                                 health=bot_health.channel("tg"))
            tasks.append(asyncio.create_task(tg_poller.run(), name="tg-poller"))

        # Название источника для подписи копий: «Автор …, переслано из …».
        # Берём из ownership бота (in-memory, без сети).
        dispatcher.source_title = make_source_title_provider(max_own, tg_own)
        # Полная отвязка источника из mini-app: удалить ownership у бота + выйти из чата.
        set_source_unbinder(make_source_unbinder(max_own, tg_own))

        # Реакция на сбой доставки: MAX не присылает событие об изменении прав бота, поэтому о
        # проблеме (чаще всего — у бота сняли права на отправку) узнаём по ОШИБКЕ отправки.
        # Правило при этом НЕ отключаем — один раз уведомляем владельца. Для канала без
        # известного отправителя шлём идентичности аккаунта-владельца правила в этом мессенджере.
        def _resolve_owner(messenger, chat_id, account_id):
            own = max_own if messenger == "max" else tg_own
            base_chat_id, _thread_id = parse_chat_key(chat_id) if messenger == "tg" else (chat_id, None)
            owner = own.owner_of(base_chat_id) if own else None
            if owner is None and account_id:
                for m, uid in store.identities_of(account_id):
                    if m == messenger:
                        owner = uid
                        break
            return own, owner, base_chat_id, _thread_id

        def _display_title(messenger, own, chat_id, base_chat_id, thread_id):
            title = (own.title_of(base_chat_id) if own else None) or str(base_chat_id)
            return topic_title(title, thread_id) if messenger == "tg" and thread_id is not None else title

        def _notice_ref(m, res, fallback_chat):
            """Ссылка на отправленное уведомление для последующего удаления (или None)."""
            if m == "max" and isinstance(res, dict):
                mid = ((res.get("message") or {}).get("body") or {}).get("mid")
                return {"messenger": "max", "mid": mid} if mid is not None else None
            if m == "tg" and isinstance(res, dict) and res.get("message_id") is not None:
                return {"messenger": "tg", "mid": res["message_id"],
                        "chat": (res.get("chat") or {}).get("id", fallback_chat)}
            return None

        async def _notify_all_messengers(recipients, text, hide_payload):
            """Разослать уведомление во все мессенджеры из recipients={messenger: uid};
            вернуть список ссылок на отправленные сообщения (для удаления при восстановлении)."""
            refs = []
            for m, uid in recipients.items():
                try:
                    res = await source_notifier(m, uid, text, hide_payload=hide_payload)
                except Exception:  # noqa: BLE001
                    log.warning("уведомление не доставлено (%s)", m, exc_info=True)
                    continue
                ref = _notice_ref(m, res, uid)
                if ref:
                    refs.append(ref)
            return refs or None

        async def _on_delivery_error(messenger, chat_id, account_id):
            """Уведомление о сбое доставки — во ВСЕ привязанные мессенджеры аккаунта (если
            привязаны оба); в мессенджере сбойной цели приоритетен владелец чата. Кнопка
            «Скрыть» ре-армит ЭТУ цель. Возвращает список ссылок на сообщения — чтобы удалить
            их все, когда доставка восстановится."""
            own, owner, base_chat_id, thread_id = _resolve_owner(messenger, chat_id, account_id)
            recipients = store.identities_by_messenger(account_id) if account_id else {}
            if owner is not None:
                recipients[messenger] = owner
            if not recipients:
                return None
            title = _display_title(messenger, own, chat_id, base_chat_id, thread_id)
            return await _notify_all_messengers(
                recipients,
                f"⚠️ Не удалось отправить сообщение в «{title}» — возможно, на принимающей "
                "стороне неполадки. Проверьте права бота на отправку сообщений.",
                f"hide_warn:{messenger}:{chat_id}")

        async def _on_delivery_clear(messenger, chat_id, ref):
            """Доставка восстановилась (или уведомление скрыто) → удалить отправленные ранее
            сообщения о сбое во всех мессенджерах. ref — список ссылок (или одиночная ссылка
            старого формата); повторное удаление уже удалённого сообщения просто логируется."""
            refs = ref if isinstance(ref, list) else [ref]
            for r in refs:
                if not isinstance(r, dict) or r.get("mid") is None:
                    continue
                m = r.get("messenger") or messenger
                try:
                    if m == "max" and max_client is not None:
                        await max_client.delete_message(r["mid"])
                    elif m == "tg" and tg_client is not None:
                        await tg_client.delete_message(r.get("chat"), r["mid"])
                except Exception:  # noqa: BLE001
                    log.warning("удаление уведомления о сбое не удалось (%s)", m, exc_info=True)

        async def _on_tg_rights_warn(chat_id, account_id, reason):
            """ПРОАКТИВНО (по событию my_chat_member): у бота в TG-чате изъято значимое право.
            Источник/правило НЕ отключаем — просим владельца вернуть право. Уведомление — во все
            мессенджеры аккаунта (владелец чата приоритетен в TG). Возвращает список ссылок на
            сообщения — чтобы удалить их, когда права вернут (через тот же _on_delivery_clear)."""
            own, owner, base_chat_id, thread_id = _resolve_owner("tg", chat_id, account_id)
            recipients = store.identities_by_messenger(account_id) if account_id else {}
            if owner is not None:
                recipients["tg"] = owner
            if not recipients:
                return None
            title = _display_title("tg", own, chat_id, base_chat_id, thread_id)
            return await _notify_all_messengers(
                recipients,
                f"⚠️ В «{title}» у бота изъято {reason}. Источник остаётся привязанным — верните "
                "это право, чтобы синхронизация продолжала работать.",
                f"hide_warn:tg:{chat_id}")

        async def _on_tg_chat_migrated(old_id, new_id):
            """Группа повышена до супергруппы — Telegram сменил chat_id. Координатор: переносим
            ВЛАДЕНИЕ (ownership) и перепривязываем ПРАВИЛА/состояние warning'а на новый id, чтобы
            доставка, баннер и проактивное отслеживание прав продолжили работать. Идемпотентно —
            зовётся и проактивно (сервисный сигнал в observe), и реактивно (ошибка доставки)."""
            if tg_own is not None:
                await tg_own.migrate_chat(old_id, new_id)
            await dispatcher.on_tg_chat_migrated(old_id, new_id)

        if tg_own is not None:
            tg_own.on_chat_migrated = _on_tg_chat_migrated      # проактивно: сервисный сигнал миграции
        dispatcher.chat_migrated_cb = _on_tg_chat_migrated      # реактивно: self-heal по ошибке доставки
        dispatcher.delivery_error_cb = _on_delivery_error
        dispatcher.delivery_clear_cb = _on_delivery_clear
        dispatcher.tg_rights_warn_cb = _on_tg_rights_warn

        _MOD_CAT_LABEL = {
            "drugs": "наркотики", "weapons": "оружие/поддельные документы",
            "extremism": "экстремизм", "csam": "запрещённый контент",
            "violence": "призывы к насилию", "fraud": "мошенничество",
            "war": "призывы к сдаче/дезертирству или вербовка", "other": "нарушение правил",
        }

        async def _on_moderation_block(messenger, chat_id, account_ids, category, reason):
            """Уведомить владельца(ев), что сообщение из источника не переслано модерацией.
            Во все привязанные мессенджеры аккаунта; кнопка «Скрыть» просто убирает сообщение."""
            label = _MOD_CAT_LABEL.get(category, "нарушение правил")
            for account_id in account_ids or []:
                recipients = store.identities_by_messenger(account_id) if account_id else {}
                if not recipients:
                    continue
                await _notify_all_messengers(
                    recipients,
                    f"🛡 Сообщение из вашего источника не переслано: модерация определила "
                    f"нарушение ({label}). Если это ошибка — напишите в поддержку.",
                    "hide_msg")

        dispatcher.moderation_block_cb = _on_moderation_block

        # --- биллинг подписки (ЮKassa) ---
        # Триал за привязку автоплатежа, оплата виджетом, автопродление в момент
        # истечения. Ключи магазина — YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY (.env).
        from control.billing import Billing
        from control.yookassa import YooKassaClient
        yk_client = YooKassaClient(cc.YOOKASSA_SHOP_ID, cc.YOOKASSA_SECRET_KEY,
                                   cc.YOOKASSA_API_BASE)
        stack.push_async_callback(yk_client.aclose)

        async def _billing_notify(acc_id, title, subtitle=None):
            """Событие биллинга: в историю mini-app + личкой во все мессенджеры аккаунта."""
            try:
                await store.add_notification(acc_id, type="sub", title=title,
                                             subtitle=subtitle or "",
                                             link={"screen": "subscription"})
            except Exception:  # noqa: BLE001
                log.warning("billing: уведомление в историю не записано", exc_info=True)
            text = f"💳 {title}" + (f"\n{subtitle}" if subtitle else "")
            for m, uid in store.identities_by_messenger(acc_id).items():
                try:
                    await notifier_fn(m, uid, text)
                except Exception:  # noqa: BLE001
                    log.warning("billing: уведомление не доставлено (%s)", m, exc_info=True)

        billing = Billing(store, yk_client, price_rub=cc.PRICE_RUB, trial_days=cc.TRIAL_DAYS,
                          return_url=cc.PAY_RETURN_URL,
                          renew_retry_seconds=cc.RENEW_RETRY_SECONDS,
                          renew_max_attempts=cc.RENEW_MAX_ATTEMPTS,
                          renew_window_days=cc.RENEW_WINDOW_DAYS, notify=_billing_notify,
                          paused_provider=lambda: settings.get("payments_paused"))
        set_billing(billing)
        # Коды активации подписки (месяц без привязки карты) — работают независимо
        # от ЮKassa; уведомления — тем же путём, что события биллинга.
        from control.activation import Activation
        set_activation(Activation(store, notify=_billing_notify))
        if billing.enabled:
            log.info("Оплата ЮKassa включена: цена %d ₽/мес, триал %d дн.",
                     cc.PRICE_RUB, cc.TRIAL_DAYS)
        else:
            log.info("Оплата ЮKassa выключена (ключи YOOKASSA_* не заданы)")

        # --- Яндекс Маркет: автоматическая выдача цифровых кодов ---
        # Webhook только пишет PROCESSING-заказ в store; сетевой воркер получает детали,
        # закрепляет коды и вызывает deliverDigitalGoods. Повтор/рестарт безопасен: набор
        # кодов хранится в market_orders и переиспользуется.
        from control.yandex_market import YandexMarketClient, YandexMarketDigital
        yandex_market = None
        if not cc.YANDEX_MARKET_ENABLED:
            set_yandex_market(None)
            log.info("Яндекс Маркет выключен (MESYNC_YANDEX_MARKET_ENABLED=false)")
        else:
            ym_client = YandexMarketClient(
                cc.YANDEX_MARKET_API_KEY,
                business_id=cc.YANDEX_MARKET_BUSINESS_ID,
                campaign_id=cc.YANDEX_MARKET_CAMPAIGN_ID,
                base_url=cc.YANDEX_MARKET_API_BASE,
                timeout=cc.YANDEX_MARKET_TIMEOUT,
            )
            stack.push_async_callback(ym_client.aclose)
            yandex_market = YandexMarketDigital(
                store,
                ym_client,
                sku=cc.YANDEX_MARKET_SKU,
                activation_url=cc.YANDEX_MARKET_ACTIVATION_URL,
            )
            set_yandex_market(yandex_market)
            if yandex_market.enabled and cc.YANDEX_MARKET_WEBHOOK_SECRET:
                log.info("Яндекс Маркет включён: campaign=%s, business=%s, SKU=%s",
                         cc.YANDEX_MARKET_CAMPAIGN_ID, cc.YANDEX_MARKET_BUSINESS_ID,
                         cc.YANDEX_MARKET_SKU)
            else:
                log.info("Яндекс Маркет выключен (MESYNC_YANDEX_MARKET_* заданы не полностью)")

        # --- жалобы на контент + операции модерации (этапы 3–4) ---
        # Reports создаём ВСЕГДА: воркер + операции нужны админ-панели (список/действия/
        # классификация/автопауза). Ссылку «Пожаловаться» и приём жалоб включает runtime-
        # настройка moderation_reports_enabled (dispatcher._reports_on / эндпоинт /api/report).
        # MAX перечитываем по API. Для Telegram API чтения по id нет; fallback берёт только
        # локальный normalized content.jsonl, если бот уже видел этот update.
        from control.content_lookup import lookup_tg_content_text
        async def _report_fetch_text(messenger, chat_id, mid):
            """Актуальный/локально сохранённый текст сообщения для жалоб."""
            if messenger == "tg":
                return await lookup_tg_content_text(cc.TG_CONTENT_FILE, chat_id, mid)
            if messenger != "max" or max_client is None:
                return None
            try:
                msg = await max_client.get_message(mid)
            except Exception:  # noqa: BLE001 — удалено/нет доступа → недоступно
                log.warning("жалоба: не перечитать текст MAX %s", mid, exc_info=True)
                return None
            if not isinstance(msg, dict):
                return None
            m = msg.get("message") if isinstance(msg.get("message"), dict) else msg
            return ((m or {}).get("body") or {}).get("text") or ""

        def _is_already_hidden_error(exc: Exception) -> bool:
            text = str(exc).lower()
            return "not modified" in text or "не измен" in text

        async def _report_hide_copy(messenger, chat_id, mid):
            """Скрыть свою копию нарушающего контента без удаления сообщения.

            MAX API умеет убрать вложения через attachments=[] при PUT /messages. Telegram Bot
            API не умеет удалить медиа из media-сообщения без deleteMessage; вместо этого пробуем
            заменить media на PNG-заглушку, а если тип альбома не позволяет — меняем caption.
            """
            try:
                if messenger == "max" and max_client is not None:
                    await max_client.edit_message(
                        mid, text=HIDDEN_VIOLATION_TEXT, attachments=[], notify=False)
                    return True
                if messenger == "tg" and tg_client is not None:
                    try:
                        await tg_client.edit_message_text(
                            chat_id, mid, HIDDEN_VIOLATION_TEXT, parse_mode=None,
                            disable_web_page_preview=True)
                    except Exception as exc:  # noqa: BLE001
                        if _is_already_hidden_error(exc):
                            return True
                        media_error = exc
                        try:
                            await tg_client.edit_message_media(chat_id, mid, {
                                "type": "photo",
                                "media": UploadFile(_TG_HIDDEN_MEDIA_PNG, filename="hidden.png",
                                                    content_type="image/png"),
                                "caption": HIDDEN_VIOLATION_TEXT,
                            })
                            return True
                        except Exception as media_exc:  # noqa: BLE001
                            if _is_already_hidden_error(media_exc):
                                return True
                            media_error = media_exc
                        try:
                            await tg_client.edit_message_caption(
                                chat_id, mid, HIDDEN_VIOLATION_TEXT, parse_mode=None)
                        except Exception as caption_exc:  # noqa: BLE001
                            if _is_already_hidden_error(caption_exc):
                                return True
                            raise caption_exc from media_error
                    return True
            except Exception:  # noqa: BLE001
                log.warning("жалоба: не скрыть копию %s:%s:%s", messenger, chat_id, mid,
                            exc_info=True)
            return False

        async def _report_chat_member_ok(messenger, chat_id):
            """Preflight жалобы: бот всё ещё состоит в Telegram-чате копии.

            Telegram Bot API getChatMember(chat_id, user_id) возвращает ChatMember со status
            (creator/administrator/member/restricted/left/kicked). Если бот удалён из группы,
            обычно будет left/kicked или ошибка доступа; в обоих случаях показываем заглушку.
            """
            if messenger != "tg":
                return None
            if tg_client is None or tg_bot_id is None:
                return False
            try:
                member = await tg_client.get_chat_member(chat_id, tg_bot_id)
            except Exception:  # noqa: BLE001
                log.info("жалоба: бот не найден/нет доступа к TG-чату %s", chat_id, exc_info=True)
                return False
            status = str((member or {}).get("status") or "").lower()
            return status not in {"left", "kicked"}

        async def _report_source_admin_ok(messenger, chat_id, user_id):
            """Админ источника может скрыть сообщение своей жалобой без ИИ/ручной проверки.

            Проверяем только same-messenger identity: TG user_id валиден только для TG-источника,
            MAX user_id — только для MAX-источника.
            """
            if messenger == "tg":
                if tg_client is None:
                    return False
                try:
                    member = await tg_client.get_chat_member(chat_id, user_id)
                except Exception:  # noqa: BLE001
                    log.info("жалоба: не проверить TG-админа источника %s user=%s",
                             chat_id, user_id, exc_info=True)
                    return False
                status = str((member or {}).get("status") or "").lower()
                return status in {"administrator", "creator"}
            if messenger == "max":
                if max_client is None:
                    return False
                marker = None
                for _ in range(20):  # защита от битой пагинации API
                    try:
                        page = await max_client.get_chat_admins(chat_id, marker=marker)
                    except Exception:  # noqa: BLE001
                        log.info("жалоба: не проверить MAX-админа источника %s user=%s",
                                 chat_id, user_id, exc_info=True)
                        return False
                    for member in (page or {}).get("members") or []:
                        if str(member.get("user_id")) == str(user_id) and (
                            member.get("is_owner") or member.get("is_admin")
                        ):
                            return True
                    marker = (page or {}).get("marker")
                    if marker in (None, ""):
                        break
                return False
            return False

        async def _on_report_violation(account_id, category, reason):
            """Уведомить владельца правила, что его копия скрыта по жалобе (нарушение)."""
            label = _MOD_CAT_LABEL.get(category, "нарушение правил")
            recipients = store.identities_by_messenger(account_id) if account_id else {}
            if not recipients:
                return
            await _notify_all_messengers(
                recipients,
                f"🛡 По жалобе читателя ваша пересланная копия скрыта модерацией "
                f"(нарушение: {label}). Если это ошибка — напишите в поддержку.",
                "hide_msg")

        async def _on_autopause(rule_id, account_id, count):
            """Автопауза правила по страйкам — уведомить владельца (moderation_hold уже выставлен)."""
            recipients = store.identities_by_messenger(account_id) if account_id else {}
            if not recipients:
                return
            await _notify_all_messengers(
                recipients,
                f"🛡 Пересылка по одному из ваших правил приостановлена модерацией "
                f"({count} нарушений за сутки). Проверьте контент источника и напишите в поддержку.",
                "hide_msg")

        reports = Reports(store, moderation=dispatcher._moderation, message_map=message_map,
                          fetch_text=_report_fetch_text, hide_copy=_report_hide_copy,
                          notify_owner=_on_report_violation,
                          chat_member_ok=_report_chat_member_ok,
                          source_admin_ok=_report_source_admin_ok,
                          service_log=service_log,
                          settings=settings, stoplist=dispatcher._stoplist, hold_cb=_on_autopause)
        set_reports(reports)
        log.info("Модерация: воркер жалоб + операции админ-панели активны (приём жалоб — %s)",
                 "включён" if cc.MODERATION_REPORTS_ENABLED else "по настройке панели")

        # --- рассылки в личные чаты (этап 4.6) ---
        # Тот же notifier_fn, что биллинг/модерация → доставка ТОЛЬКО в личку (в источники нет).
        broadcaster = Broadcaster(store, send=notifier_fn, settings=settings)
        set_broadcaster(broadcaster)

        # --- control-API ---
        app = create_app(store)
        uconfig = uvicorn.Config(app, host=cc.API_HOST, port=cc.API_PORT, log_level="warning", access_log=False)
        server = uvicorn.Server(uconfig)
        server_task = asyncio.create_task(server.serve(), name="control-api")
        tasks.append(server_task)
        log.info("control-API на http://%s:%s/api", cc.API_HOST, cc.API_PORT)

        # Фоновый дебаунс-сброс реестра «своих» сообщений на диск (переживает рестарты).
        tasks.append(asyncio.create_task(sent_index.run(), name="sent-index-flush"))
        tasks.append(asyncio.create_task(message_map.run(), name="message-map-flush"))

        # Биллинг: продление подписки в момент истечения + дожим незавершённых
        # оплат/привязок (fallback на случай не настроенного вебхука ЮKassa).
        async def _billing_loop():
            while True:
                try:
                    await billing.tick()
                except Exception:  # noqa: BLE001
                    log.warning("billing loop: сбой", exc_info=True)
                await asyncio.sleep(30)

        if billing.enabled:
            tasks.append(asyncio.create_task(_billing_loop(), name="billing-loop"))

        if (yandex_market is not None and yandex_market.enabled
                and cc.YANDEX_MARKET_WEBHOOK_SECRET):
            tasks.append(asyncio.create_task(yandex_market.run(), name="yandex-market-worker"))

        # Воркер очереди жалоб (наполняется из стора → переживает рестарт).
        if reports is not None:
            reports.load_pending()
            tasks.append(asyncio.create_task(reports.run(), name="reports-worker"))

        # Воркер рассылок (незавершённые резюмируются по курсору при старте).
        broadcaster.load_pending()
        tasks.append(asyncio.create_task(broadcaster.run(), name="broadcaster"))

        if max_client is not None and cc.REGISTRATION_REMINDER_DELAYS:
            reminders = RegistrationReminderWorker(
                store, messenger="max", delays=cc.REGISTRATION_REMINDER_DELAYS,
                interval=cc.REGISTRATION_REMINDER_INTERVAL,
                batch_limit=cc.REGISTRATION_REMINDER_BATCH,
                send=_send_max_registration_reminder)
            tasks.append(asyncio.create_task(reminders.run(), name="registration-reminders"))

        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop.set)

        log.info("Запущено: задач=%d. Ctrl+C для остановки.", len(tasks))
        stop_task = asyncio.create_task(stop.wait(), name="shutdown-signal")
        done, pending = await asyncio.wait([stop_task, *tasks],
                                           return_when=asyncio.FIRST_COMPLETED)
        # Фоновая задача упала с исключением (а не остановлена сигналом) → отчёт в сервисный
        # канал ДО завершения процесса (дальше systemd перезапустит сервис). Best-effort.
        for tsk in done:
            exc = None if tsk.cancelled() else tsk.exception()
            if exc is not None:
                log.error("Задача %s упала: %r", tsk.get_name(), exc)
                # В персистентную ленту событий (переживёт рестарт — процесс сейчас завершится).
                with contextlib.suppress(Exception):
                    await store.add_event(kind="crash",
                                          title=f"Падение задачи {tsk.get_name()}",
                                          detail=repr(exc))
                await service_log.report(
                    "Падение фоновой задачи",
                    [f"Задача: <code>{tsk.get_name()}</code>",
                     "Процесс завершится и будет перезапущен systemd."],
                    error=exc)
        server.should_exit = True
        if not server_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(server_task), timeout=5)
            except asyncio.TimeoutError:
                log.warning("control-API не завершился за 5 секунд; задача будет отменена")
        if not stop_task.done():
            stop_task.cancel()
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(stop_task, return_exceptions=True)
        await asyncio.gather(*tasks, return_exceptions=True)
        await sent_index.flush()                # финальный сброс реестра на диск
        await message_map.flush()
    log.info("Остановлено.")


async def _amain() -> None:
    store = ControlStore()
    await store.start()
    log.info("ControlStore backend: %s", store.backend)
    try:
        await _run(store)
    finally:
        await store.close()


def main() -> None:
    _setup_logging()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_amain())


if __name__ == "__main__":
    main()
