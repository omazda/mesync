"""Runtime-подстановка публичной конфигурации в frontend HTML."""
from __future__ import annotations

import html
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import config


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _with_query(url: str, key: str, value: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def public_config() -> dict[str, object]:
    return {
        "botName": config.BOT_NAME,
        "botAvatarUrl": config.BOT_AVATAR_URL,
        "appUrl": config.APP_URL,
        "botLinks": dict(config.BOT_URLS),
        "botHandles": dict(config.BOT_HANDLES),
        "support": {
            "telegramUrl": config.SUPPORT_TG_URL,
            "telegramHandle": config.SUPPORT_TG_HANDLE,
            "email": config.SUPPORT_EMAIL,
        },
        "legal": {
            "termsVersion": config.LEGAL_TERMS_VERSION,
            "privacyVersion": config.LEGAL_PRIVACY_VERSION,
        },
        "landing": {
            "description": config.LANDING_DESCRIPTION,
            "offerTitle": config.LANDING_OFFER_TITLE,
            "offerText": config.LANDING_OFFER_TEXT,
            "analyticsNotice": config.LANDING_ANALYTICS_NOTICE,
        },
        "trackers": {
            "vkAds": {
                "enabled": bool(config.VK_ADS_PIXEL_ID),
                "pixelId": config.VK_ADS_PIXEL_ID,
                "utmSource": config.VK_ADS_UTM_SOURCE,
            },
        },
    }


def _json_for_script(value: object) -> str:
    # Не позволяем значению из .env закрыть inline-script через `</script>`.
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def public_config_script() -> str:
    """Return a cache-safe script loaded before either React application."""
    return f"window.__MESYNC_PUBLIC_CONFIG__={_json_for_script(public_config())};\n"


def _support_lines(language: str) -> list[str]:
    lines: list[str] = []
    if config.SUPPORT_EMAIL:
        label = "Электронная почта" if language == "ru" else "Email"
        email = _escape(config.SUPPORT_EMAIL)
        lines.append(f'{label}: <a href="mailto:{email}">{email}</a>')
    if config.SUPPORT_TG_URL:
        label = _escape(config.SUPPORT_TG_HANDLE or config.SUPPORT_TG_URL)
        lines.append(
            f'Telegram: <a href="{_escape(config.SUPPORT_TG_URL)}">{label}</a>')
    return lines


def _provider_lines(language: str) -> list[str]:
    name = (config.LEGAL_PROVIDER_NAME_EN or config.LEGAL_PROVIDER_NAME_RU) \
        if language == "en" else config.LEGAL_PROVIDER_NAME_RU
    lines: list[str] = []
    if name:
        lines.append(_escape(name))
    if config.LEGAL_TAX_ID:
        lines.append(f'{"ИНН" if language == "ru" else "TIN"}: {_escape(config.LEGAL_TAX_ID)}')
    if config.LEGAL_REGISTRATION_ID:
        label = "ОГРНИП" if language == "ru" else "Registration number"
        lines.append(f"{label}: {_escape(config.LEGAL_REGISTRATION_ID)}")
    return lines


def _legal_fragments() -> dict[str, str]:
    ru_provider = _provider_lines("ru")
    en_provider = _provider_lines("en")
    ru_support = _support_lines("ru")
    en_support = _support_lines("en")
    ru_identity = ", ".join(ru_provider) or "Владелец текущего развёртывания Сервиса"
    en_identity = ", ".join(en_provider) or "The owner of the current Service deployment"
    ru_details = ru_provider + ru_support or ["Сведения заполняются владельцем развёртывания."]
    en_details = en_provider + en_support or ["Details are provided by the deployment owner."]
    ru_controller = ru_provider or ["владелец текущего развёртывания Сервиса"]
    en_controller = en_provider or ["the owner of the current Service deployment"]

    return {
        "__MESYNC_LEGAL_OFFER_INTRO_RU__": (
            f"<p>{ru_identity}, далее — «Исполнитель», предлагает пользователю сервиса "
            f"{_escape(config.BOT_NAME)} заключить настоящее соглашение на условиях "
            "публичной оферты.</p>"),
        "__MESYNC_LEGAL_OFFER_INTRO_EN__": (
            f'<p>{en_identity}, hereinafter referred to as the "Contractor", offers the user '
            f"of the {_escape(config.BOT_NAME)} service to enter into this agreement under "
            "the terms of a public offer.</p>"),
        "__MESYNC_LEGAL_REQUISITES_RU__": (
            f'<p class="requisites">{"<br />".join(ru_details)}</p>'),
        "__MESYNC_LEGAL_REQUISITES_EN__": (
            f'<p class="requisites">{"<br />".join(en_details)}</p>'),
        "__MESYNC_LEGAL_CONTROLLER_RU__": (
            '<p class="requisites">Оператором персональных данных является:<br />'
            f'{"<br />".join(ru_controller + ru_support)}</p>'),
        "__MESYNC_LEGAL_CONTROLLER_EN__": (
            '<p class="requisites">The personal data controller is:<br />'
            f'{"<br />".join(en_controller + en_support)}</p>'),
        "__MESYNC_SUPPORT_CONTACT_RU__": (
            f"<p>{'По вопросам обработки и удаления данных, отзыва согласия и направления претензий Пользователь может обратиться: ' + '; '.join(ru_support) + '.' if ru_support else 'Контакты для обращений задаются владельцем развёртывания Сервиса.'}</p>"),
        "__MESYNC_SUPPORT_CONTACT_EN__": (
            f"<p>{'For questions about data processing, deletion, consent withdrawal, and claims, the User may contact: ' + '; '.join(en_support) + '.' if en_support else 'Contact details are configured by the Service deployment owner.'}</p>"),
        **_tracker_legal_fragments(),
    }


def _tracker_legal_fragments() -> dict[str, str]:
    if not config.VK_ADS_PIXEL_ID:
        return {
            "__MESYNC_TRACKER_DATA_RU__": "",
            "__MESYNC_TRACKER_DATA_EN__": "",
            "__MESYNC_TRACKER_PURPOSE_RU__": "",
            "__MESYNC_TRACKER_PURPOSE_EN__": "",
            "__MESYNC_TRACKER_THIRD_PARTY_RU__": "",
            "__MESYNC_TRACKER_THIRD_PARTY_EN__": "",
            "__MESYNC_TRACKER_COOKIES_RU__": "",
            "__MESYNC_TRACKER_COOKIES_EN__": "",
        }
    return {
        "__MESYNC_TRACKER_DATA_RU__": (
            " На публичной посадочной странице также могут обрабатываться адрес и "
            "источник перехода, UTM-метки, технические сведения о браузере и устройстве, "
            "случайный ClientID и события выбора MAX или Telegram."),
        "__MESYNC_TRACKER_DATA_EN__": (
            " The public landing page may also process the page address and referral "
            "source, UTM tags, browser and device details, a random ClientID, and MAX or "
            "Telegram selection events."),
        "__MESYNC_TRACKER_PURPOSE_RU__": (
            " Данные рекламной аналитики используются для оценки источников трафика, "
            "эффективности кампаний и выбора пользователями MAX или Telegram."),
        "__MESYNC_TRACKER_PURPOSE_EN__": (
            " Advertising analytics data is used to evaluate traffic sources, campaign "
            "performance, and whether visitors choose MAX or Telegram."),
        "__MESYNC_TRACKER_THIRD_PARTY_RU__": (
            '<p>8.6. ООО «ВК» через Счётчик Mail (Top.Mail.Ru), используемый VK Ads, — '
            "для рекламной и маркетинговой аналитики публичной страницы.</p>"),
        "__MESYNC_TRACKER_THIRD_PARTY_EN__": (
            "<p>8.6. VK LLC through Mail Counter (Top.Mail.Ru), used by VK Ads, for "
            "advertising and marketing analytics of the public page.</p>"),
        "__MESYNC_TRACKER_COOKIES_RU__": (
            f"<p>10.3. На публичной странице {_escape(config.BOT_NAME)} используется "
            "рекламный счётчик VK Ads / Top.Mail.Ru. Он фиксирует просмотр страницы и "
            "переход по кнопке в MAX или Telegram, использует адрес и источник перехода "
            "для атрибуции кампании и может устанавливать cookie со случайным ClientID. "
            'Условия обработки приведены в <a href="https://help.mail.ru/legal/terms/top/pp/">'
            "политике конфиденциальности Счётчика Mail</a>.</p>"
            "<p>10.4. Публичная страница показывает уведомление об аналитике. Ограничить "
            "или удалить аналитические cookies можно в настройках браузера; это не "
            "ограничивает переход в мессенджеры и использование Сервиса.</p>"),
        "__MESYNC_TRACKER_COOKIES_EN__": (
            f"<p>10.3. The public {_escape(config.BOT_NAME)} page uses the VK Ads / "
            "Top.Mail.Ru advertising counter. It records page views and clicks leading to "
            "MAX or Telegram, uses the page address and referral source for campaign "
            "attribution, and may set a cookie with a random ClientID. Processing terms "
            'are described in the <a href="https://help.mail.ru/legal/terms/top/pp/">'
            "Mail Counter privacy policy</a>.</p>"
            "<p>10.4. The public page displays an analytics notice. Analytics cookies can "
            "be restricted or deleted in browser settings without preventing access to "
            "the messengers or the Service.</p>"),
    }


def _browser_links() -> str:
    links: list[str] = []
    if config.BOT_URLS["max"]:
        url = _with_query(config.BOT_URLS["max"], "start", "web")
        links.append(
            f'<a class="static-entry-action max" href="{_escape(url)}">'
            f'Открыть {_escape(config.BOT_NAME)} в MAX</a>')
    if config.BOT_URLS["tg"]:
        url = _with_query(config.BOT_URLS["tg"], "start", "web")
        links.append(
            f'<a class="static-entry-action telegram" href="{_escape(url)}">'
            f'Открыть {_escape(config.BOT_NAME)} в Telegram</a>')
    return "\n          ".join(links) if links else (
        '<p class="static-entry-note">Ссылки на ботов не настроены.</p>')


def _avatar_html() -> str:
    if not config.BOT_AVATAR_URL:
        return ""
    url = _escape(config.BOT_AVATAR_URL)
    return (f'<img class="static-entry-logo" src="{url}" width="88" height="88" '
            f'alt="Логотип {_escape(config.BOT_NAME)}" />')


def _favicon_html() -> str:
    if not config.BOT_AVATAR_URL:
        return ""
    url = _escape(config.BOT_AVATAR_URL)
    return (f'<link rel="icon" href="{url}" />\n'
            f'  <link rel="apple-touch-icon" href="{url}" />')


def _landing_offer_html() -> str:
    if not config.LANDING_OFFER_TITLE and not config.LANDING_OFFER_TEXT:
        return ""
    title = (f"<strong>{_escape(config.LANDING_OFFER_TITLE)}</strong>"
             if config.LANDING_OFFER_TITLE else "")
    return f'<p class="static-entry-offer">{title}{_escape(config.LANDING_OFFER_TEXT)}</p>'


def _landing_analytics_notice_html() -> str:
    if not config.VK_ADS_PIXEL_ID or not config.LANDING_ANALYTICS_NOTICE:
        return ""
    return f'<p class="static-entry-analytics">{_escape(config.LANDING_ANALYTICS_NOTICE)}</p>'


def _landing_json_ld() -> str:
    data: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": config.BOT_NAME,
        "url": f"{config.APP_URL.rstrip('/')}/",
        "description": config.LANDING_DESCRIPTION,
        "applicationCategory": "BusinessApplication",
    }
    bot_links = [url for url in config.BOT_URLS.values() if url]
    if bot_links:
        data["sameAs"] = bot_links
    return _json_for_script(data)


def render_public_html(source: str) -> str:
    replacements = {
        "__MESYNC_BOT_NAME__": _escape(config.BOT_NAME),
        "__MESYNC_APP_URL__": _escape(f"{config.APP_URL.rstrip('/')}/"),
        "__MESYNC_LANDING_DESCRIPTION__": _escape(config.LANDING_DESCRIPTION),
        "__MESYNC_LANDING_OFFER__": _landing_offer_html(),
        "__MESYNC_LANDING_ANALYTICS_NOTICE__": _landing_analytics_notice_html(),
        "__MESYNC_LANDING_JSON_LD__": _landing_json_ld(),
        "__MESYNC_BROWSER_BOT_LINKS__": _browser_links(),
        "__MESYNC_BROWSER_AVATAR__": _avatar_html(),
        "__MESYNC_FAVICON_LINKS__": _favicon_html(),
        **_legal_fragments(),
    }
    rendered = source
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered
