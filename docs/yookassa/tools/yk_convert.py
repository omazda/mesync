# Конвертация скачанных страниц документации ЮKassa (HTML) в Markdown
# с сохранением всего текста, таблиц и блоков кода. Крупные inline-SVG
# (диаграммы) сохраняются отдельными файлами рядом с .md.
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

SRC = Path('yk-html')
DST = Path('/root/sync-bot/docs/yookassa/markdown')
BASE = 'https://yookassa.ru'
SAVED_AT = '2026-07-02'


class Conv(MarkdownConverter):
    def convert_pre(self, el, text, *args, **kwargs):
        code = el.get_text()
        if not code.strip():
            return ''
        return '\n```\n' + code.rstrip('\n') + '\n```\n'


def url_for(slug: str) -> str:
    return f'{BASE}/developers/payment-acceptance/' + slug.replace('__', '/')


def convert_one(html_path: Path) -> tuple[str, str, int, int]:
    slug = html_path.stem
    rel = Path(slug.replace('__', '/') + '.md')
    out_path = DST / rel
    out_path.parent.mkdir(parents=True, exist_ok=True)

    soup = BeautifulSoup(html_path.read_text(encoding='utf-8'), 'html.parser')
    art = soup.find('article')
    assert art is not None, slug
    pre_count = len(art.find_all('pre'))

    # мусор UI: пустые кнопки (копирование кода)
    for b in art.find_all('button'):
        b.decompose()
    # SVG: крупные (диаграммы) — в файлы, мелкие (иконки) — удалить
    svg_n = 0
    for svg in art.find_all('svg'):
        raw = str(svg)
        if len(raw) > 3000:
            svg_n += 1
            assets = out_path.parent / 'assets'
            assets.mkdir(parents=True, exist_ok=True)
            svg_file = assets / f'{out_path.stem}-diagram-{svg_n}.svg'
            svg_file.write_text(raw, encoding='utf-8')
            img = soup.new_tag('img', src=f'assets/{svg_file.name}', alt=f'диаграмма {svg_n}')
            svg.replace_with(img)
        else:
            svg.decompose()
    # ссылки и картинки → абсолютные URL (кроме локальных assets)
    page_url = url_for(slug)
    for a in art.find_all('a', href=True):
        a['href'] = urljoin(page_url, a['href'])
    for img in art.find_all('img'):
        src = img.get('src') or ''
        if src and not src.startswith('assets/'):
            img['src'] = urljoin(page_url, src)

    md = Conv(heading_style='ATX', bullets='-').convert(str(art))
    md = re.sub(r'\n{3,}', '\n\n', md).strip() + '\n'

    title = art.find('h1')
    title = title.get_text(strip=True) if title else slug
    header = (f'<!-- Источник: {page_url} -->\n'
              f'<!-- Полная копия статьи официальной документации ЮKassa, сохранено {SAVED_AT} -->\n\n')
    out_path.write_text(header + md, encoding='utf-8')

    fence_pairs = md.count('```') // 2
    return str(rel), title, pre_count, fence_pairs


results = []
for f in sorted(SRC.glob('*.html')):
    if f.stem in ('yk-test', 'yk-test-ru'):
        continue
    results.append(convert_one(f))

print(f'{"файл":68} {"pre":>4} {"```":>4}')
ok = True
for rel, title, pre, fen in results:
    mark = 'OK' if pre == fen else '!!'
    if pre != fen:
        ok = False
    print(f'{rel:68} {pre:>4} {fen:>4} {mark}  {title[:45]}')
print('ALL OK' if ok else 'MISMATCH FOUND')
