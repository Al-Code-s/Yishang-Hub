"""把 docs/user-guide.md 渲染成可直接给客户看的单文件网页。

用法：
    python scripts/build_user_guide.py            # 生成网页（两份副本）
    python scripts/build_user_guide.py --check    # 只校验是否最新（不写文件）

产出：
    docs/user-guide.html        独立单文件，可直接双击打开 / 邮件发送给客户
    frontend/public/guide.html  随前端一起发布，访问 /guide.html

设计约束：
* 只用 Python 标准库，不引入 npm 或 pip 依赖；
* 输出**完全自包含**（CSS/JS 内联，无 CDN、无外链字体），离线可看；
* 只支持 docs/user-guide.md 实际用到的 Markdown 子集，不做通用实现。
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "docs" / "user-guide.md"
OUTPUTS = (REPO_ROOT / "docs" / "user-guide.html", REPO_ROOT / "frontend" / "public" / "guide.html")

CJK = r"\u4e00-\u9fff"
CJK_RANGES = ((0x3000, 0x303F), (0x4E00, 0x9FFF), (0xFF00, 0xFFEF))


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return any(low <= code <= high for low, high in CJK_RANGES)


def join_wrapped(parts: list[str]) -> str:
    """把被硬换行的同一段落/列表项接回去。

    Markdown 会把行内换行当作空格，但中文之间插入空格会多出空隙，
    所以「两侧都是中日韩字符」时不加空格，其余情况仍加空格。
    """
    if not parts:
        return ""
    out = parts[0]
    for part in parts[1:]:
        if not out or not part:
            out += part
            continue
        if _is_cjk(out[-1]) and _is_cjk(part[0]):
            out += part
        else:
            out += " " + part
    return out


def escape(text: str) -> str:
    return html.escape(text, quote=False)


def slugify(text: str) -> str:
    cleaned = re.sub(r"[`*]", "", text)
    cleaned = re.sub(r"[^0-9A-Za-z" + CJK + r"]+", "-", cleaned).strip("-")
    return (cleaned or "section").lower()


def inline(text: str) -> str:
    """行内标记：`code`、**bold**、[text](url)。

    先把代码片段换成占位符，再做加粗/斜体/链接，最后回填——这样
    ``**…… `code` ……**`` 这种「加粗里含行内代码」也能正确渲染。
    """
    codes: list[str] = []

    def stash(match: re.Match[str]) -> str:
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    work = re.sub(r"`([^`]+)`", stash, text)
    seg = escape(work)
    seg = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", seg, flags=re.S)
    seg = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", seg)
    seg = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        seg,
    )
    for index, code in enumerate(codes):
        seg = seg.replace(f"\x00{index}\x00", "<code>" + escape(code) + "</code>")
    return seg


def _is_table_sep(line: str) -> bool:
    return bool(re.match(r"^\|[\s:\-|]+\|$", line.strip())) and "-" in line


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _aligns(sep: str) -> list[str]:
    result = []
    for cell in _cells(sep):
        left, right = cell.startswith(":"), cell.endswith(":")
        result.append("center" if left and right else "right" if right else "left")
    return result


def convert(md: str) -> tuple[str, list[tuple[int, str, str]]]:
    """返回 (正文 HTML, [(层级, 锚点, 标题)])。"""
    lines = md.splitlines()
    toc: list[tuple[int, str, str]] = []
    used: dict[str, int] = {}
    body: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            body.append('<pre class="ys-code"><code>' + escape("\n".join(code)) + "</code></pre>")
            continue

        if stripped.startswith("<!--"):
            body.append(stripped)
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            anchor = slugify(text)
            used[anchor] = used.get(anchor, 0) + 1
            if used[anchor] > 1:
                anchor = f"{anchor}-{used[anchor]}"
            if level >= 2:
                toc.append((level, anchor, text))
            body.append(
                f'<h{level} id="{anchor}">{inline(text)}'
                f'<a class="ys-anchor" href="#{anchor}" aria-label="链接到此节">#</a>'
                f"</h{level}>"
            )
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            header = _cells(stripped)
            aligns = _aligns(lines[i + 1])
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            head_html = "".join(
                f'<th style="text-align:{aligns[n] if n < len(aligns) else "left"}">{inline(c)}</th>'
                for n, c in enumerate(header)
            )
            body_html = []
            for row in rows:
                tds = "".join(
                    f'<td style="text-align:{aligns[n] if n < len(aligns) else "left"}">{inline(c)}</td>'
                    for n, c in enumerate(row)
                )
                body_html.append(f"<tr>{tds}</tr>")
            body.append(
                '<div class="ys-table-wrap"><table><thead><tr>'
                + head_html
                + "</tr></thead><tbody>"
                + "".join(body_html)
                + "</tbody></table></div>"
            )
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while i < len(lines) and (lines[i].strip().startswith(">") or not lines[i].strip()):
                if not lines[i].strip():
                    if i + 1 < len(lines) and lines[i + 1].strip().startswith(">"):
                        quote.append("")
                        i += 1
                        continue
                    break
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            chunks: list[str] = []
            current: list[str] = []
            for entry in quote:
                if not entry.strip():
                    if current:
                        chunks.append(join_wrapped(current))
                        current = []
                    continue
                current.append(entry.strip())
            if current:
                chunks.append(" ".join(current))
            body.append(
                "<blockquote>"
                + "".join(f"<p>{inline(c)}</p>" for c in chunks)
                + "</blockquote>"
            )
            continue

        if re.match(r"^[-*]\s+", stripped):
            items: list[list[str]] = []
            while i < len(lines):
                cur = lines[i]
                if re.match(r"^\s*[-*]\s+", cur):
                    items.append([re.sub(r"^\s*[-*]\s+", "", cur)])
                    i += 1
                    continue
                if cur.strip() and re.match(r"^\s{2,}\S", cur) and items:
                    items[-1].append(cur.strip())
                    i += 1
                    continue
                break
            body.append(
                "<ul>"
                + "".join(f"<li>{inline(join_wrapped(chunks))}</li>" for chunks in items)
                + "</ul>"
            )
            continue

        ordered = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if ordered:
            items2: list[list[str]] = []
            while i < len(lines):
                cur = lines[i]
                m = re.match(r"^\s*\d+\.\s+(.*)$", cur)
                if m:
                    items2.append([m.group(1)])
                    i += 1
                    continue
                if cur.strip() and re.match(r"^\s{2,}\S", cur) and items2:
                    items2[-1].append(cur.strip())
                    i += 1
                    continue
                break
            body.append(
                "<ol>"
                + "".join(f"<li>{inline(join_wrapped(chunks))}</li>" for chunks in items2)
                + "</ol>"
            )
            continue

        if not stripped:
            i += 1
            continue

        para: list[str] = []
        while i < len(lines):
            cur = lines[i]
            s = cur.strip()
            if not s or s.startswith(("```", ">", "|", "#")) or re.match(r"^[-*]\s+", s):
                break
            if re.match(r"^\d+\.\s+", s) and para:
                break
            if re.match(r"^<!--", s):
                break
            para.append(s)
            i += 1
        if para:
            body.append("<p>" + inline(join_wrapped(para)) + "</p>")
            continue
        i += 1

    return "\n".join(body), toc


def build_toc(entries: list[tuple[int, str, str]]) -> str:
    rows: list[str] = []
    depth = 2
    for level, anchor, text in entries:
        if level > depth and rows:
            rows.append("<ul>")
            depth = level
        while level < depth:
            rows.append("</ul>")
            depth -= 1
        cls = "ys-toc__l2" if level == 2 else "ys-toc__l3"
        rows.append(
            f'<li class="{cls}"><a href="#{anchor}" data-target="{anchor}">{escape(text)}</a></li>'
        )
    while depth > 2:
        rows.append("</ul>")
        depth -= 1
    return '<ul class="ys-toc__root">' + "".join(rows) + "</ul>"

CSS = """
:root{--navy:#0b2545;--navy2:#12395f;--navy3:#1b4c7e;--blue:#1668dc;--blue-l:#e8f1fd;--blue-d:#12509b;--g50:#f6f8fa;--g100:#eef1f5;--g200:#e2e6ec;--g300:#d3d9e2;--g500:#6b7684;--g700:#3c4653;--ink:#1f2937;--r:10px;--sh:0 1px 2px rgba(16,42,74,.05),0 1px 6px rgba(16,42,74,.04)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--g50);color:var(--ink);font:15px/1.78 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif}
.ys-top{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:16px;min-height:56px;padding:8px 22px;background:linear-gradient(90deg,var(--navy) 0%,var(--navy2) 55%,var(--navy3) 100%);color:#fff;box-shadow:0 2px 10px rgba(11,37,69,.18)}
.ys-top__brand{font-size:16px;font-weight:600;letter-spacing:.3px;white-space:nowrap}
.ys-top__meta{margin-left:auto;font-size:12.5px;opacity:.82;text-align:right}
.ys-top__btn{border:1px solid rgba(255,255,255,.45);background:transparent;color:#fff;font-size:13px;padding:5px 12px;border-radius:6px;cursor:pointer;white-space:nowrap}
.ys-top__btn:hover{background:rgba(255,255,255,.14)}
.ys-wrap{display:grid;grid-template-columns:288px minmax(0,1fr);gap:22px;max-width:1440px;margin:22px auto 60px;padding:0 22px;align-items:start}
.ys-toc{position:sticky;top:78px;max-height:calc(100vh - 104px);overflow:auto;background:#fff;border:1px solid var(--g200);border-radius:var(--r);box-shadow:var(--sh);padding:14px}
.ys-toc__title{font-size:13px;font-weight:600;color:var(--g500);letter-spacing:.5px;margin:0 0 8px;display:flex;justify-content:space-between;align-items:center}
.ys-toc__search{width:100%;padding:7px 10px;margin-bottom:10px;border:1px solid var(--g200);border-radius:6px;font-size:13px;outline:none;background:var(--g50)}
.ys-toc__search:focus{border-color:var(--blue);background:#fff}
.ys-toc ul{list-style:none;margin:0;padding:0}
.ys-toc li{margin:1px 0}
.ys-toc a{display:block;padding:4px 8px;border-radius:6px;color:var(--g700);text-decoration:none;font-size:13px;line-height:1.5;border-left:2px solid transparent}
.ys-toc a:hover{background:var(--blue-l);color:var(--blue-d)}
.ys-toc a.is-active{background:var(--blue-l);color:var(--blue-d);font-weight:600;border-left-color:var(--blue)}
.ys-toc .ys-toc__l3 a{padding-left:20px;font-size:12.5px;color:var(--g500)}
.ys-toc li.is-hidden{display:none}
.ys-doc{background:#fff;border:1px solid var(--g200);border-radius:var(--r);box-shadow:var(--sh);padding:10px 42px 48px;min-width:0}
.ys-banner{margin:18px 0 6px;padding:12px 16px;background:var(--blue-l);border:1px solid #cfe1fa;border-radius:8px;color:var(--blue-d);font-size:13.5px}
.ys-doc h1{font-size:25px;line-height:1.4;margin:18px 0 14px;color:var(--navy);font-weight:600}
.ys-doc h2{font-size:20px;margin:38px 0 14px;padding:0 0 10px;border-bottom:1px solid var(--g200);color:var(--navy);font-weight:600}
.ys-doc h3{font-size:16.5px;margin:26px 0 10px;color:var(--navy3);font-weight:600}
.ys-doc h2:first-of-type{margin-top:12px}
.ys-anchor{margin-left:8px;color:var(--g300);font-weight:400;text-decoration:none;opacity:0;font-size:.8em}
.ys-doc h1:hover .ys-anchor,.ys-doc h2:hover .ys-anchor,.ys-doc h3:hover .ys-anchor{opacity:1}
.ys-doc p{margin:10px 0}
.ys-doc ul,.ys-doc ol{margin:10px 0;padding-left:26px}
.ys-doc li{margin:5px 0}
.ys-doc li::marker{color:var(--blue)}
.ys-doc a{color:var(--blue-d);text-decoration:none;border-bottom:1px solid #bcd6f7}
.ys-doc a:hover{border-bottom-color:var(--blue)}
.ys-doc strong{color:var(--navy);font-weight:600}
.ys-doc code{background:var(--g100);color:var(--blue-d);padding:1.5px 5px;border-radius:4px;font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,"Courier New",monospace;word-break:break-word}
.ys-code{background:#0b2545;color:#e6eef8;padding:14px 16px;border-radius:8px;overflow:auto;margin:14px 0;box-shadow:inset 0 0 0 1px rgba(255,255,255,.06)}
.ys-code code{background:none;color:inherit;padding:0;font-size:13px;line-height:1.7;white-space:pre}
.ys-doc blockquote{margin:14px 0;padding:11px 16px;background:#f8fbff;border-left:4px solid var(--blue);border-radius:0 8px 8px 0;color:var(--g700)}
.ys-doc blockquote p{margin:5px 0}
.ys-table-wrap{overflow-x:auto;margin:14px 0;border:1px solid var(--g200);border-radius:8px}
.ys-doc table{border-collapse:collapse;width:100%;font-size:14px}
.ys-doc th{background:var(--blue-l);color:var(--navy);font-weight:600;text-align:left;padding:9px 12px;border-bottom:1px solid var(--g200);white-space:nowrap}
.ys-doc td{padding:8px 12px;border-bottom:1px solid var(--g100);vertical-align:top}
.ys-doc tbody tr:last-child td{border-bottom:none}
.ys-doc tbody tr:nth-child(even){background:#fbfcfe}
.ys-doc tbody tr:hover{background:#f4f8fe}
.ys-foot{max-width:1440px;margin:0 auto 40px;padding:0 22px;color:var(--g500);font-size:12.5px;text-align:center}
.ys-top-btn{position:fixed;right:22px;bottom:26px;z-index:25;width:42px;height:42px;border-radius:50%;border:1px solid var(--g200);background:#fff;color:var(--navy);cursor:pointer;box-shadow:0 6px 18px rgba(11,37,69,.16);font-size:17px;display:none}
.ys-top-btn.is-on{display:block}
@media (max-width:1024px){.ys-wrap{grid-template-columns:1fr}.ys-toc{position:static;max-height:none}.ys-doc{padding:6px 20px 32px}.ys-top__meta{display:none}}
@media print{.ys-top,.ys-toc,.ys-top-btn{display:none!important}.ys-wrap{display:block;max-width:none;margin:0;padding:0}.ys-doc{border:none;box-shadow:none;padding:0}.ys-doc h2{page-break-after:avoid}.ys-table-wrap,.ys-code{page-break-inside:avoid}}
"""

JS = """
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('.ys-toc a[data-target]'));
  var map = {};
  links.forEach(function (a) { map[a.getAttribute('data-target')] = a; });
  var heads = Array.prototype.slice.call(document.querySelectorAll('.ys-doc h2[id], .ys-doc h3[id]'));
  function setActive(id) {
    links.forEach(function (a) { a.classList.remove('is-active'); });
    if (map[id]) {
      map[id].classList.add('is-active');
      var box = document.querySelector('.ys-toc');
      var top = map[id].offsetTop - box.clientHeight / 2;
      if (Math.abs(box.scrollTop - top) > box.clientHeight / 2) { box.scrollTop = Math.max(top, 0); }
    }
  }
  if ('IntersectionObserver' in window) {
    var seen = {};
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { seen[e.target.id] = e.isIntersecting ? e.boundingClientRect.top : null; });
      var current = null;
      heads.forEach(function (h) { if (seen[h.id] !== null && seen[h.id] !== undefined && current === null) { current = h.id; } });
      if (current) { setActive(current); }
    }, { rootMargin: '-72px 0px -70% 0px', threshold: 0 });
    heads.forEach(function (h) { observer.observe(h); });
  }
  var search = document.querySelector('.ys-toc__search');
  if (search) {
    search.addEventListener('input', function () {
      var q = search.value.trim().toLowerCase();
      Array.prototype.slice.call(document.querySelectorAll('.ys-toc li')).forEach(function (li) {
        var hit = !q || li.textContent.toLowerCase().indexOf(q) >= 0;
        li.classList.toggle('is-hidden', !hit);
      });
    });
  }
  var topBtn = document.querySelector('.ys-top-btn');
  window.addEventListener('scroll', function () {
    topBtn.classList.toggle('is-on', window.scrollY > 600);
  });
  topBtn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  var printBtn = document.querySelector('[data-action="print"]');
  if (printBtn) { printBtn.addEventListener('click', function () { window.print(); }); }
})();
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="scripts/build_user_guide.py">
<meta name="robots" content="noindex, nofollow">
<title>意尚智造集成平台 · 使用说明</title>
<style>
__CSS__
</style>
</head>
<body>
<header class="ys-top">
  <div class="ys-top__brand">意尚智造集成平台 · 使用说明</div>
  <button class="ys-top__btn" data-action="print">打印 / 导出 PDF</button>
  <div class="ys-top__meta">最后更新：__DATE__</div>
</header>
<div class="ys-wrap">
  <nav class="ys-toc">
    <p class="ys-toc__title"><span>目录</span><span>__COUNT__ 节</span></p>
    <input class="ys-toc__search" type="search" placeholder="搜索小节…" aria-label="搜索小节">
    __TOC__
  </nav>
  <main class="ys-doc">
    <div class="ys-banner">本页是<b>平台使用说明</b>，可以离线打开，也可以直接打印或导出 PDF 分发给同事。</div>
__BODY__
  </main>
</div>
<p class="ys-foot">意尚智造集成平台 · 使用说明</p>
<button class="ys-top-btn" title="回到顶部">↑</button>
<script>
__JS__
</script>
</body>
</html>
"""


def render(md: str) -> str:
    body, toc = convert(md)
    match = re.search(r"最后更新：\**\s*(\d{4}-\d{2}-\d{2})", md)
    date = match.group(1) if match else "未标注"
    return (
        TEMPLATE.replace("__CSS__", CSS.strip())
        .replace("__JS__", JS.strip())
        .replace("__TOC__", build_toc(toc))
        .replace("__BODY__", body)
        .replace("__DATE__", date)
        .replace("__COUNT__", str(len(toc)))
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="渲染 docs/user-guide.md 为单文件网页")
    parser.add_argument("--check", action="store_true", help="只校验产出是否最新，不写文件")
    args = parser.parse_args(argv)

    md = SOURCE.read_text(encoding="utf-8")
    page = render(md)

    if args.check:
        stale = []
        for out in OUTPUTS:
            if not out.is_file() or out.read_text(encoding="utf-8") != page:
                stale.append(out)
        if stale:
            for out in stale:
                print(f"过期: {out.relative_to(REPO_ROOT)}")
            print("请运行： python scripts/build_user_guide.py")
            return 1
        print("使用说明网页版是最新的。")
        return 0

    for out in OUTPUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8", newline="\n")
        print(f"已生成 {out.relative_to(REPO_ROOT)}（{len(page)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
