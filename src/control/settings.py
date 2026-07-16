"""Runtime-настройки админ-панели (settings-store).

Слой поверх дефолтов `config`: администратор меняет значения из панели, и они применяются
мгновенно, без перезапуска процесса. Значения хранятся в таблице `settings` стора
(`ControlStore`), эффективное значение = оверрайд из стора ЛИБО дефолт из `config`.

Меняются ТОЛЬКО ключи из белого списка `_SPEC` (тип + валидация). Расширяется по мере
подключения потребителей в следующих под-фазах (модерация, тарифы, лимиты).
"""
from __future__ import annotations

from typing import Any, Callable

from . import config


class SettingsError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# Белый список runtime-параметров. default — вызываемый (читает актуальный config).
_SPEC: dict[str, dict[str, Any]] = {
    # Глобальная приостановка приёма платежей: новые оплаты и автопродление на паузе
    # (коды активации не затрагиваются). См. billing.paused_provider.
    "payments_paused": {"type": "bool", "default": lambda: False},
    # Режим предотправочного гейта модерации (off/shadow/enforce) — RuleDispatcher._gate_mode.
    "moderation_gate_mode": {"type": "enum", "values": ("off", "shadow", "enforce"),
                             "default": lambda: config.MODERATION_GATE_MODE},
    # Глобальный флаг ИИ-классификации: влияет и на предотправочный гейт, и на обработку жалоб.
    "moderation_ai_enabled": {"type": "bool", "default": lambda: True},
    # Жалобы читателей: ссылка «Пожаловаться» под копиями + приём жалоб.
    "moderation_reports_enabled": {"type": "bool",
                                   "default": lambda: config.MODERATION_REPORTS_ENABLED},
    # Порог автопаузы правила: N подтверждённых нарушений за 24 ч → moderation_hold.
    "moderation_autopause_strikes": {"type": "int", "min": 1, "max": 100, "default": lambda: 3},
    # Темп рассылок в личные чаты, сообщений/с. Потолок 30 = лимит MAX API (общий с трафиком
    # моста), потому дефолт 20 — с запасом. Потребитель: control.broadcasts.Broadcaster.
    "broadcast_rate_limit": {"type": "int", "min": 1, "max": 30, "default": lambda: 20},
}


class Settings:
    def __init__(self, store: Any) -> None:
        self.store = store

    def _default(self, key: str) -> Any:
        return _SPEC[key]["default"]()

    def _validate(self, key: str, value: Any) -> Any:
        spec = _SPEC[key]
        t = spec["type"]
        if t == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            raise SettingsError("Ожидается логическое значение.")
        if t == "enum":
            v = str(value)
            if v not in spec["values"]:
                raise SettingsError("Недопустимое значение.")
            return v
        if t == "int":
            try:
                v = int(value)
            except (TypeError, ValueError):
                raise SettingsError("Ожидается целое число.")
            if "min" in spec and v < spec["min"]:
                raise SettingsError(f"Минимум {spec['min']}.")
            if "max" in spec and v > spec["max"]:
                raise SettingsError(f"Максимум {spec['max']}.")
            return v
        raise SettingsError("Неизвестный тип параметра.")

    def validate(self, key: str, value: Any) -> Any:
        """Проверить ключ+значение БЕЗ записи (для двухфазного атомарного PUT). Возвращает
        нормализованное значение или бросает SettingsError."""
        if key not in _SPEC:
            raise SettingsError("Неизвестный параметр.")
        return self._validate(key, value)

    def get(self, key: str) -> Any:
        """Эффективное значение: оверрайд из стора или дефолт из config."""
        if key not in _SPEC:
            raise SettingsError("Неизвестный параметр.")
        raw = self.store.settings_all().get(key)
        if raw is None:
            return self._default(key)
        try:
            return self._validate(key, raw)   # хранимое уже валидно, но нормализуем тип
        except SettingsError:
            return self._default(key)          # битый оверрайд → дефолт (fail-safe)

    def all(self) -> dict[str, Any]:
        """Все эффективные значения (для GET /api/admin/settings)."""
        return {k: self.get(k) for k in _SPEC}

    async def set(self, key: str, value: Any) -> Any:
        """Проверить и сохранить оверрайд. Возвращает применённое значение."""
        if key not in _SPEC:
            raise SettingsError("Неизвестный параметр.")
        val = self._validate(key, value)
        await self.store.set_setting(key, val)
        return val
