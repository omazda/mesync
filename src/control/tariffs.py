"""Единые отображаемые условия тарифа для API, billing и уведомлений."""
from __future__ import annotations

from . import config

SMART_PLAN = "smart"
INDIVIDUAL_PLAN = "individual"


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(int(n))
    if 11 <= n_abs % 100 <= 14:
        return many
    last = n_abs % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def fmt_bytes_ru(n: int) -> str:
    """Компактный размер для описания лимита: «0,5 ТБ», «100 ГБ», «37 МБ»."""
    n = max(0, int(n or 0))
    tb = n / 1024 ** 4
    if tb >= 0.45:
        s = f"{tb:.1f}".rstrip("0").rstrip(".")
        return f"{s.replace('.', ',')} ТБ"
    gb = n / 1024 ** 3
    if gb >= 1:
        s = f"{gb:.1f}".rstrip("0").rstrip(".")
        return f"{s.replace('.', ',')} ГБ"
    return f"{max(1, round(n / 1024 ** 2))} МБ"


def is_individual(*, price: int, rule_limit: int, traffic_limit: int) -> bool:
    return (
        int(price) != int(config.PRICE_RUB)
        or int(rule_limit) != int(config.RULE_LIMIT)
        or int(traffic_limit) != int(config.TRAFFIC_LIMIT_BYTES)
    )


def plan_id(individual: bool, fallback: str = SMART_PLAN) -> str:
    return INDIVIDUAL_PLAN if individual else (fallback or SMART_PLAN)


def plan_name(individual: bool) -> str:
    return "Индивидуальный" if individual else "Smart"


def payment_title(individual: bool) -> str:
    return plan_name(individual)


def rule_limit_text(rule_limit: int) -> str:
    word = plural_ru(rule_limit, "правило", "правила", "правил")
    return f"До {int(rule_limit)} {word} пересылки"


def traffic_limit_text(traffic_limit: int) -> str:
    return f"{fmt_bytes_ru(traffic_limit)} медиа-трафика за месяц"


def perks(*, rule_limit: int, traffic_limit: int) -> list[str]:
    return [
        rule_limit_text(rule_limit),
        traffic_limit_text(traffic_limit),
        "MAX ⇄ Telegram в обе стороны",
        "Чистая копия: без пометки „переслано“",
        "Подпись отправителя для групп",
    ]
