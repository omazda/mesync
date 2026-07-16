"""Тесты стоп-словаря / нормализатора (src/control/stoplist.py).

Запуск:  .venv/bin/python -m pytest tests/test_stoplist.py -q
"""
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="stop_test_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:T")
os.environ.setdefault("MAX_BOT_TOKEN", "m")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.stoplist import StopList, normalize  # noqa: E402
from control.moderation import CATEGORIES  # noqa: E402

_YAML = """
categories:
  drugs:
    terms: [мефедрон, закладк]
    words: [лсд, меф]
    spaced: [закладк, мефедрон]
    phrases: [магазин закладок]
  violence:
    terms: [зареж, зарез]
    phrases: [убить всех]
  profanity:
    terms: [бляд, еб]
"""


def _write(text: str) -> Path:
    p = _TMP / f"sl_{time.time_ns()}.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def _sl() -> StopList:
    return StopList(str(_write(_YAML)))


# ---------------- нормализатор ----------------

def test_normalize_lower_yo_homoglyph():
    assert normalize("МёД")[0] == "мед"
    norm2, _ = normalize("mecoc")   # латиница→кириллица
    assert "с" in norm2 and "е" in norm2


def test_normalize_compact_strips_separators():
    assert normalize("н.а.р.к.о")[1] == "нарко"
    assert normalize("н а р к о")[1] == "нарко"


def test_normalize_collapses_repeats():
    assert "ррр" not in normalize("нарррко")[0]


# ---------------- корни (terms) ----------------

def test_root_matches_word_form():
    sl = _sl()
    assert "drugs" in sl.match("оставил закладку в парке")   # стемминг
    assert "drugs" in sl.match("продам мефедрон")


def test_spaced_matches_inside_word_tradeoff():
    sl = _sl()
    # spaced (compact) осознанно ловит подстроку — плата за устойчивость к разрядке.
    # Обычные корни (не в spaced) границу слова соблюдают — см. test_eb/test_zarezh ниже.
    assert "drugs" in sl.match("текстперезакладкапарк")


def test_root_leet_obfuscation():
    sl = _sl()
    assert "drugs" in sl.match("meфeдрoн есть")   # гомоглифы→кириллица


# ---------------- words (точное слово) ----------------

def test_word_exact_token():
    sl = _sl()
    assert "drugs" in sl.match("нужен лсд сегодня")


def test_word_not_substring():
    sl = _sl()
    assert "drugs" not in sl.match("влсделать")     # лсд внутри слова — нет
    assert "drugs" not in sl.match("лсдешный")      # с хвостом — тоже нет (точное слово)


# ---------------- spaced (разрядка) ----------------

def test_spaced_obfuscation():
    sl = _sl()
    assert "drugs" in sl.match("з а к л а д к а готова")
    assert "drugs" in sl.match("м-е-ф-е-д-р-о-н")


# ---------------- phrases ----------------

def test_phrase_match_with_filler():
    sl = _sl()
    assert "drugs" in sl.match("наш магазин закладок")
    assert "drugs" in sl.match("магазин с закладками")   # одно служебное слово между
    assert "violence" in sl.match("призыв убить всех сейчас")


def test_phrase_stemming():
    sl = _sl()
    assert "violence" in sl.match("надо убить всех врагов")


def test_phrase_matches_inflected_forms():
    # фраза в косвенном падеже должна ловиться (основы, не полные слова)
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    assert "fraud" in sl.match("ЦБ предупредил о новой финансовой пирамиде")
    assert "fraud" in sl.match("обещают гарантированную прибыль всем")


# ---------------- FP-регрессии (предупреждения критика-сорсинга) ----------------

def test_no_fp_clean_message():
    sl = _sl()
    assert sl.match("Завтра встреча в парке, приносите настроение") == set()


def test_eb_root_no_fp_on_common_words():
    # «еб» как начало слова НЕ должно ловить хлеб/небо/требовать/серебро
    sl = _sl()
    assert "profanity" not in sl.match("хлеб и небо над лесом")
    assert "profanity" not in sl.match("надо требовать серебро")


def test_eb_root_catches_profanity():
    sl = _sl()
    assert "profanity" in sl.match("да он ебанулся совсем")


def test_zarezh_no_fp_across_words():
    # «зареж» по началу слова: «на базаре же» не должно ловиться (в отличие от compact)
    sl = _sl()
    assert "violence" not in sl.match("на базаре же было весело")
    assert "violence" in sl.match("я тебя зарежу")


def test_multiple_categories():
    sl = _sl()
    hits = sl.match("продам мефедрон и грозится зарезать")
    assert "drugs" in hits and "violence" in hits


# ---------------- боевой словарь ----------------

def test_production_yaml_loads_and_categories_valid():
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    cats = set(sl.loaded_categories)
    assert cats, "боевой словарь должен загрузиться"
    # категории словаря — из CATEGORIES модерации (+ отдельная profanity)
    assert cats <= (set(CATEGORIES) | {"profanity"})
    assert {"drugs", "weapons", "extremism", "violence", "fraud", "war", "profanity"} <= cats


def test_production_yaml_positive_signals():
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    assert "drugs" in sl.match("куплю мефедрон закладкой")
    assert "weapons" in sl.match("сделаю поддельный паспорт на чужое имя")
    assert "weapons" in sl.match("Продам пистолет")
    assert "extremism" in sl.match("вступай, зиг хайль, братья")
    assert "violence" in sl.match("призываю убить всех")
    assert "violence" in sl.match("Взорвать трансформатор")
    assert "fraud" in sl.match("вложись в финансовую пирамиду, гарантированный доход")
    assert "war" in sl.match("солдат, сдавайся в плен, звони на горячую линию сдачи")
    assert "war" in sl.match("работа кладменом на всу, оплата за поджог военкомата")
    assert "profanity" in sl.match("что за хуйня творится")


def test_production_yaml_no_fp_on_news_and_daily():
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    # обычные бытовые/новостные фразы не должны триггерить тяжёлые категории
    for text in [
        "Сегодня хорошая погода, гуляли в парке с детьми",
        "Правительство обсудило новый закон о налогах",
        "Купил хлеб, молоко и серебряную ложку",
        "Сел на колени перед бабушкой",
        "Команда собрала мандарины на рынке",
    ]:
        hits = sl.match(text)
        heavy = hits - {"profanity"}
        assert heavy == set(), f"ложное срабатывание на: {text!r} → {heavy}"


# ---------------- устойчивость / хот-релоад ----------------

def test_missing_file_is_empty_noop():
    sl = StopList(str(_TMP / "nope.yaml"))
    assert sl.match("мефедрон закладка") == set()
    assert sl.loaded_categories == ()


def test_none_path_is_empty():
    assert StopList(None).match("мефедрон") == set()


def test_broken_yaml_is_empty_not_crash():
    sl = StopList(str(_write("categories: [not: valid: {")))
    assert sl.match("мефедрон") == set()


def test_flat_format_supported():
    sl = StopList(str(_write("drugs: [мефедрон]\n")))
    assert sl.match("мефедрон") == {"drugs"}


def test_hot_reload_on_change():
    p = _write("drugs:\n  terms: [мефедрон]\n")
    sl = StopList(str(p))
    assert sl.match("гашиш") == set()
    p.write_text("drugs:\n  terms: [мефедрон, гашиш]\n", encoding="utf-8")
    os.utime(p, None)
    sl._checked_at = 0.0   # имитируем истёкшее окно троттлинга reload (в бою — до 2 c)
    assert "drugs" in sl.match("гашиш")   # перезагрузился по (mtime,size)


def test_reload_keeps_snapshot_on_transient_oserror():
    p = _write("drugs:\n  terms: [мефедрон]\n")
    sl = StopList(str(p))
    assert "drugs" in sl.match("мефедрон")
    p.unlink()                              # файл временно исчез (редактор пересоздаёт)
    sl._checked_at = 0.0
    assert "drugs" in sl.match("мефедрон")   # снапшот сохранён, а не обнулён


def test_scalar_yaml_value_not_iterated_char_by_char():
    # terms: мефедрон (скаляр, не список) не должен стать однобуквенным regex «на всё»
    sl = StopList(str(_write("drugs:\n  terms: мефедрон\n")))
    assert "drugs" in sl.match("продам мефедрон")
    assert sl.match("мама мыла раму") == set()   # не ловит обычные слова


# ---------------- обфускация и FP (находки ревью этапа 2) ----------------

def test_leet_digit_3_is_ze():
    # «3акладка» (3 вместо З) — частая русская обфускация → должна ловиться
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    assert "drugs" in sl.match("оставил 3акладку во дворе")


def test_latin_transliteration_lsd_mdma():
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    assert "drugs" in sl.match("продам lsd и mdma оптом")
    assert "drugs" in sl.match("zakladka gotova")   # закладка латиницей


def test_no_fp_review_cases():
    # FP-регрессии из ревью этапа 2 (не должны триггерить тяжёлые категории)
    sl = StopList(config.MODERATION_STOPLIST_FILE)
    for text in [
        "зарезервируйте столик в ресторане на вечер",   # зарез→зареза (не зарезервировать)
        "склад менеджера уже закрыт",                    # кладмен убран из spaced
        "герои нашего времени — прекрасный роман",       # героин убран из spaced
        "пробивной нападающий забил гол",                # пробив убран из корней
        "убитого горем человека все жалели",             # фраза «убить всех» без длинного филлера
        "россияне не воюют за чужие интересы",           # фраза «не воюй за» через стемминг
    ]:
        heavy = sl.match(text) - {"profanity"}
        assert heavy == set(), f"ложное срабатывание: {text!r} → {heavy}"
