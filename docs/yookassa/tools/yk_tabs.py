# Пост-обработка markdown-копий ЮKassa: серверный HTML рендерит только первый
# таб примера (обычно cURL), остальные варианты (PHP/Python/JavaScript/HTML)
# лежат в Markdoc-AST внутри window.__data__. Здесь:
#   1) каждому fence-блоку проставляется язык из AST (```bash / ```json / …);
#   2) группа меток-табов перед блоком разворачивается в ПОЛНЫЙ набор блоков
#      («**cURL**: код», «**PHP**: код», «**Python**: код»).
import json
import re
from pathlib import Path

MD_ROOT = Path('/root/sync-bot/docs/yookassa/markdown')
HTML_ROOT = Path('yk-html')

LABELS = {'cURL', 'PHP', 'Python', 'JavaScript', 'HTML', 'JSON', 'XML', 'Swift', 'Java', 'Kotlin'}
LABEL_LANGS = {
    'cURL': ('bash', 'curl', 'shell', 'sh'),
    'PHP': ('php',),
    'Python': ('python', 'py'),
    'JavaScript': ('javascript', 'js'),
    'HTML': ('html', 'markup'),
    'JSON': ('json',),
    'XML': ('xml',),
    'Swift': ('swift',),
    'Java': ('java',),
    'Kotlin': ('kotlin',),
}
# Табы-СЕКЦИИ с текстовым содержимым (не код): просто выделяются жирным.
CONTENT_TABS = {'iOS SDK', 'Android SDK'}


def _strings(node):
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return ''.join(_strings(c) for c in node)
    if isinstance(node, dict):
        return _strings(node.get('children') or [])
    return ''


def code_nodes(html: str):
    """[(lang, code)] в порядке документа — Code-теги Markdoc из window.__data__."""
    res = []
    for m in re.finditer(r'\{"\$\$mdtype":"Tag","name":"Code"', html):
        start = m.start()
        depth = 0
        i = start
        in_str = esc = False
        while i < len(html):
            ch = html[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        try:
            obj = json.loads(html[start:i + 1])
        except Exception:
            continue
        attrs = obj.get('attributes') or {}
        lang = attrs.get('lang') or attrs.get('data-language') or ''
        res.append((str(lang).lower(), _strings(obj.get('children') or [])))
    return res


def norm(s: str) -> str:
    return ''.join(s.split())


def fence(code: str, lang: str) -> str:
    return f'```{lang}\n{code.rstrip()}\n```'


def process(md_path: Path, html_path: Path):
    nodes = code_nodes(html_path.read_text(encoding='utf-8'))
    lines = md_path.read_text(encoding='utf-8').split('\n')
    out = []
    ptr = 0            # указатель по AST-узлам (порядок документа)
    i = 0
    stats = {'lang': 0, 'groups': 0, 'added': 0, 'miss': 0, 'bolded': 0}
    while i < len(lines):
        line = lines[i]
        if line.strip() != '```':
            out.append(line)
            i += 1
            continue
        # собрали fence
        j = i + 1
        while j < len(lines) and lines[j].strip() != '```':
            j += 1
        body = '\n'.join(lines[i + 1:j])
        # метки-табы прямо над блоком (через пустые строки)
        labels = []
        k = len(out) - 1
        while k >= 0:
            t = out[k].strip()
            if t == '':
                k -= 1
                continue
            if t in LABELS:
                labels.insert(0, t)
                k -= 1
                continue
            break
        # найти AST-узел этого блока
        idx = None
        for n in range(ptr, len(nodes)):
            if norm(nodes[n][1]) == norm(body):
                idx = n
                break
        if idx is None:
            stats['miss'] += 1
            out.append(line)
            out.extend(lines[i + 1:j + 1])
            i = j + 1
            continue
        group_ok = len(labels) >= 2 and idx + len(labels) <= len(nodes) and all(
            nodes[idx + t][0].startswith(LABEL_LANGS[labels[t]])
            for t in range(len(labels)))
        if group_ok:
            # выкинуть строки-метки из out (вместе с пустыми хвостами)
            while out and (out[-1].strip() == '' or out[-1].strip() in LABELS):
                out.pop()
            out.append('')
            for t, lab in enumerate(labels):
                lang, code = nodes[idx + t]
                out.append(f'**{lab}**')
                out.append('')
                out.append(fence(code, lang))
                out.append('')
                if t > 0:
                    stats['added'] += 1
            stats['groups'] += 1
            ptr = idx + len(labels)
        else:
            # одиночный блок: проставить язык; одиночную метку сделать жирной
            if len(labels) == 1:
                while out and out[-1].strip() == '':
                    out.pop()
                assert out[-1].strip() in LABELS
                out[-1] = f'**{labels[0]}**'
                out.append('')
            lang = nodes[idx][0]
            out.append(fence(nodes[idx][1] if norm(nodes[idx][1]) == norm(body) else body, lang))
            stats['lang'] += 1
            ptr = idx + 1
        i = j + 1
    # финальный проход: осиротевшие метки-табы (код без серверного рендера рядом,
    # текстовые секции iOS SDK/Android SDK) выделяем жирным; внутри fence не трогаем
    fenced = False
    for n, ln in enumerate(out):
        t = ln.strip()
        if t.startswith('```'):
            fenced = not fenced
            continue
        if not fenced and t in (LABELS | CONTENT_TABS):
            out[n] = f'**{t}**'
            stats['bolded'] = stats.get('bolded', 0) + 1
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).rstrip() + '\n'
    md_path.write_text(text, encoding='utf-8')
    return stats


total = {'lang': 0, 'groups': 0, 'added': 0, 'miss': 0, 'bolded': 0}
for html_file in sorted(HTML_ROOT.glob('*.html')):
    if html_file.stem.startswith('yk-test'):
        continue
    md_file = MD_ROOT / (html_file.stem.replace('__', '/') + '.md')
    st = process(md_file, html_file)
    for key in total:
        total[key] += st[key]
    print(f'{md_file.relative_to(MD_ROOT)!s:70} групп={st["groups"]} добавлено={st["added"]} одиночных={st["lang"]} без_пары={st["miss"]} болд={st["bolded"]}')
print('ИТОГО:', total)
