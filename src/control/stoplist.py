"""Стоп-словарь: дешёвый предфильтр текста перед ИИ-проверкой модерации.

Назначение: НЕ блок-лист, а ТРИГГЕР. Попадание слова-маркера отправляет сообщение на
ИИ-проверку (MiniMax), которая уже отличает новость/обсуждение от призыва/сбыта. Поэтому
матчер оптимизирован под низкие ложные срабатывания при разумной полноте (каждое
срабатывание тяжёлой категории = 1 запрос к ИИ = квота Token Plan).

Категории совпадают с control.moderation.CATEGORIES. Категория «profanity» (мат) —
отдельная, она НЕ эскалирует к ИИ и не блокирует (мат в группах допустим); гейт её
отбрасывает, поэтому её точность некритична (низкие ставки).

Формат YAML (все поля необязательны), пример в data/moderation/stoplist.yaml:
  categories:
    drugs:
      terms:   [мефедрон, закладк]   # КОРНИ: матч по началу слова + стемминг (закладку, закладчик)
      words:   [меф, лсд]            # ТОЧНЫЕ слова: только целым токеном (аббревиатуры, короткие)
      spaced:  [закладк, мефедрон]   # доп. матч по «сжатой» форме — ловит разрядку «з а к л а д к а»
      phrases: [магазин закладок]    # фразы: гибко (разделители + до одного служебного слова между)
Плоский вид {drugs: [...]} тоже принимается (список → terms).

Устойчивость (урок ревью этапа 1): YAML-парсер и файл словаря загружаются лениво и
безопасно — отсутствие/ошибка файла или отсутствие PyYAML не роняют пакет, а лишь дают
пустой словарь (гейт становится no-op, fail-open). Горячая перезагрузка по mtime.

Нормализация ДО матча (docs критика-сорсинга): гомоглифы латиница→кириллица, leet
цифра→буква, снятие разрядки/пунктуации внутри слова (для «spaced»), е/ё, схлопывание
повторов, нижний регистр.
"""
from __future__ import annotations

import logging
import os
import re
import time
import unicodedata

log = logging.getLogger("control.stoplist")

# Обфускация бывает двух видов, и одна таблица покрыть их не может (буквы конфликтуют):
#  1) Полная транслитерация: слово целиком латиницей (lsd, mdma, zakladka) → раскладка
#     латиница→кириллица по звучанию (n→н, h→х, p→п, r→р, u→у) + leet цифр.
#  2) Визуальные гомоглифы: кириллическое слово с вкраплением латинских двойников
#     (мeфeдрoн — e/o латиницей). Для двойников выбор иной (h→н, p→р, n→п…).
# Поэтому нормализуем текст ДВУМЯ способами и матчим по обоим (union) — см. normalize().
_TRANSLIT = str.maketrans({
    "a": "а", "b": "б", "c": "с", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п",
    "q": "к", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "х",
    "y": "у", "z": "з", "3": "з", "0": "о", "4": "ч", "6": "б", "1": "и", "@": "а", "$": "с",
})
_HOMOGLYPHS = str.maketrans({
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у",
    "k": "к", "m": "м", "t": "т", "b": "б", "h": "н", "n": "п", "r": "г",
    "u": "и", "3": "з", "0": "о", "4": "ч", "6": "б", "@": "а", "$": "с",
})
_SEP_RE = re.compile(r"[^0-9а-я]+")            # разделители (не буква/цифра кириллицы)
_REPEAT_RE = re.compile(r"(.)\1{2,}")          # 3+ повтора символа → 1 (нарркооо → нарко)
_WORD_CH = "а-я0-9"                             # класс «буква слова» после нормализации (ё→е)


def _apply(text: str, table) -> tuple[str, str]:
    t = _REPEAT_RE.sub(r"\1", text.translate(table))
    return t, _SEP_RE.sub("", t)


def normalize(text: str) -> tuple[str, str]:
    """Возвращает (normalized, compact) по ВИЗУАЛЬНОЙ раскладке (обратная совместимость).
    Полный набор форм для матчинга даёт normalize_forms()."""
    if not text:
        return "", ""
    base = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    return _apply(base, _HOMOGLYPHS)


def normalize_forms(text: str) -> tuple[tuple[str, str], ...]:
    """Все нормализованные формы (normalized, compact) — по транслитерации И по визуальным
    гомоглифам. Матчер проверяет паттерны по каждой (покрывает оба вектора обфускации)."""
    if not text:
        return (("", ""),)
    base = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")
    forms = {_apply(base, _TRANSLIT), _apply(base, _HOMOGLYPHS)}
    return tuple(forms)


def _norm_term(term: str) -> str:
    return normalize(str(term))[0].strip()


def _roots_regex(roots: list[str]) -> re.Pattern | None:
    """Матч КОРНЯ по началу слова + любой стеммингный хвост: (?<!буква)root[буквы]*."""
    alts = sorted({re.escape(r) for r in roots if r}, key=len, reverse=True)
    if not alts:
        return None
    return re.compile(rf"(?<![{_WORD_CH}])(?:{'|'.join(alts)})[{_WORD_CH}]*")


def _words_regex(words: list[str]) -> re.Pattern | None:
    """Матч ТОЧНОГО слова целиком (обе границы) — для коротких/двусмысленных аббревиатур."""
    alts = sorted({re.escape(w) for w in words if w}, key=len, reverse=True)
    if not alts:
        return None
    return re.compile(rf"(?<![{_WORD_CH}])(?:{'|'.join(alts)})(?![{_WORD_CH}])")


def _phrase_stem(word: str) -> str:
    """Лёгкая основа слова фразы: отбрасываем короткое падежное окончание у ДЛИННЫХ слов,
    чтобы ловить словоформы («финансовая пирамида» ← «финансовой пирамиде»). Короткие слова
    (≤4) НЕ режем — иначе «воюй»→«вою» ловит «воюют», «убить»→«уби» ловит «убийца» и т.п."""
    if len(word) >= 7:
        return word[:-2]
    if len(word) >= 5:
        return word[:-1]
    return word


def _phrase_regex(phrases: list[str]) -> re.Pattern | None:
    """Фраза: основы слов по порядку; между ними разделители и ДО одного КОРОТКОГО (≤3)
    служебного слова (с/на/по/и), но не длинного — иначе «убитого горем все» ловит «убить
    всех». Токены режем по любым не-буквенным символам (дефис/пунктуация)."""
    gap = rf"[^{_WORD_CH}]+(?:[{_WORD_CH}]{{1,3}}[^{_WORD_CH}]+)?"
    pats = []
    for ph in phrases:
        toks = [re.escape(_phrase_stem(w)) + rf"[{_WORD_CH}]*"
                for w in _SEP_RE.split(_norm_term(ph)) if w]
        if toks:
            pats.append(rf"(?<![{_WORD_CH}])" + gap.join(toks))
    return re.compile("|".join(pats)) if pats else None


def _as_list(value) -> list[str]:
    """YAML-значение → список строк. Скаляр (terms: мефедрон вместо [мефедрон]) → [скаляр],
    а НЕ посимвольная итерация строки (иначе однобуквенный regex ловит всё)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return [str(value)]


class StopList:
    """Матчер категорий по стоп-словарю с горячей перезагрузкой по (mtime,size)."""

    _RELOAD_INTERVAL = 2.0   # не чаще раза в N сек трогаем ФС (не блокируем loop на каждое сообщение)

    def __init__(self, path: str | None = None) -> None:
        self._path = path
        self._sig: tuple | None = None     # (st_mtime, st_size) последней загрузки
        self._checked_at = 0.0             # монотонное время последней проверки ФС
        # {category: (root_re, word_re, spaced_tuple, phrase_re)}
        self._compiled: dict[str, tuple] = {}
        if path:
            self.reload(force=True)

    @property
    def loaded_categories(self) -> tuple[str, ...]:
        return tuple(self._compiled.keys())

    def reload(self, *, force: bool = False) -> None:
        if not self._path:
            self._compiled = {}
            return
        if not force:
            now = time.monotonic()
            if self._compiled and (now - self._checked_at) < self._RELOAD_INTERVAL:
                return                     # троттлинг: не стат-им файл на каждое сообщение
            self._checked_at = now
        try:
            st = os.stat(self._path)
            sig = (st.st_mtime, st.st_size)
        except OSError:
            # Транзиентная ошибка (редактор пересоздаёт файл, сетевой маунт) — СОХРАНЯЕМ
            # последний удачный снапшот, чтобы не остаться без модерации на время окна.
            if self._sig is None:
                self._compiled = {}        # ни разу не грузили — пусто
            return
        if not force and sig == self._sig:
            return
        self._sig = sig
        self._compile(_load_yaml(self._path))

    def _compile(self, data: dict) -> None:
        cats = data.get("categories") if isinstance(data.get("categories"), dict) else data
        compiled: dict = {}
        for cat, spec in (cats or {}).items():
            terms = words = spaced = phrases = []
            if isinstance(spec, dict):
                terms = _as_list(spec.get("terms"))
                words = _as_list(spec.get("words"))
                spaced = _as_list(spec.get("spaced"))
                phrases = _as_list(spec.get("phrases"))
            elif isinstance(spec, (list, tuple, str)):
                terms = _as_list(spec)
            root_re = _roots_regex([_norm_term(x) for x in terms])
            word_re = _words_regex([_norm_term(x) for x in words])
            phrase_re = _phrase_regex(phrases)
            spaced_norm = tuple(sorted(
                {re.sub(rf"[^{_WORD_CH}]", "", _norm_term(x)) for x in spaced if _norm_term(x)},
                key=len, reverse=True))
            compiled[str(cat)] = (root_re, word_re, spaced_norm, phrase_re)
        self._compiled = compiled

    def match(self, text: str) -> set[str]:
        """Категории, чьи маркеры найдены в тексте. Проверяет ВСЕ формы нормализации
        (транслит + визуальные гомоглифы) — покрывает оба вектора обфускации."""
        self.reload()
        if not self._compiled or not text:
            return set()
        forms = normalize_forms(text)
        hits: set[str] = set()
        for cat, (root_re, word_re, spaced, phrase_re) in self._compiled.items():
            if any((root_re is not None and root_re.search(norm))
                   or (word_re is not None and word_re.search(norm))
                   or (spaced and any(s in comp for s in spaced))
                   or (phrase_re is not None and phrase_re.search(norm))
                   for norm, comp in forms):
                hits.add(cat)
        return hits


def _load_yaml(path: str) -> dict:
    """Безопасная загрузка YAML-словаря. Любая проблема → {} (гейт станет no-op)."""
    try:
        import yaml  # ленивый импорт: отсутствие пакета не роняет control
    except Exception:  # noqa: BLE001
        log.warning("stoplist: PyYAML недоступен — словарь пуст")
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        log.info("stoplist: файл %s не найден — словарь пуст", path)
        return {}
    except Exception:  # noqa: BLE001
        log.warning("stoplist: ошибка чтения %s — словарь пуст", path, exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}
