#!/usr/bin/env python3
"""docs/adp 의 Markdown 을 같은 이름의 HTML 로 굽는다.

    python docs/adp/tools/build_html.py            # 전부 다시 굽는다
    python docs/adp/tools/build_html.py --check    # 낡았으면 1 로 죽는다

⛔ HTML 을 손으로 고치지 마라. 정본은 같은 이름의 .md 이고 이 스크립트가 옮긴다.
   목차(왼쪽 메뉴)의 정본은 NAV 다 — 새 문서를 더하면 여기 한 줄을 더한다.

의존성 없는 작은 Markdown 렌더러다(문단 · 제목 · 표 · 목록 · 코드 · 인용 · 규칙선 ·
굵게 · 기울임 · 인라인 코드 · 링크, 그리고 ```cards 블록). 이 폴더가 쓰는 문법만 안다.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ADP = Path(__file__).resolve().parent.parent
SITE_TITLE = "ADP Builder — Reference"

# 왼쪽 메뉴. (묶음, [(파일명, 짧은 이름)]) — 파일명은 확장자 없이 적는다.
NAV: list[tuple[str, list[tuple[str, str]]]] = [
    ("Start here", [
        ("index", "Overview map"),
        ("00-overview", "What ADP Builder is"),
        ("01-architecture", "Architecture"),
        ("02-data-model", "Data model"),
        # ⚠ <b>이 줄만 손으로 쓴 쪽을 가리킨다.</b> works-process/ 는 이 스크립트가 굽지 않는다
        #    (아래 glob 이 docs/adp 바로 밑의 *.md 만 집는다). 그래도 사이드바에 서야 사람이 찾는다 —
        #    링크 검사는 lint 의 「파일 실존」 갈래가 받는다. ⛔ 여기에 .md 를 만들어 넣지 마라:
        #    그 순간 같은 주소를 굽는 쪽과 손으로 쓴 쪽이 둘 다 노리게 된다.
        ("works-process/index", "Work processes"),
    ]),
    ("Platform", [
        ("03-accounts-security", "Accounts & security"),
        ("04-project-setup", "Project setup"),
        ("05-claude-cli-runtime", "Claude CLI runtime"),
        ("git", "Git layer"),
        ("20-notification", "Notifications"),
        ("25-flow", "Flow integration"),
        ("26-large-repository", "Large repos & perf"),
        ("27-concurrent-edit", "Concurrent editing"),
    ]),
    ("FRD work", [
        ("06-frd-wizard", "FRD wizard"),
        ("07-frd-workbench", "FRD workbench"),
        ("08-frd-completion", "FRD completion"),
        ("09-srt", "SRT fast track"),
    ]),
    ("Handoff to dev", [
        ("10-dev-request", "Development request"),
        ("11-dev-result", "Development result"),
        ("17-tests", "Unit & integration tests"),
    ]),
    ("Reference material", [
        ("12-ia", "IA (menu tree)"),
        ("13-solution-mockup", "Solution templates"),
        ("14-design-guide", "Design guide"),
        ("15-business-language", "Policy & terms"),
        ("16-green-zone", "Green-zone artifacts"),
        ("18-screen-id", "Screen IDs"),
        ("19-checker", "Spec checker"),
        ("24-document-intake", "Intake & doc reading"),
    ]),
    ("Working on it", [
        ("21-operations", "Install & operations"),
        ("22-conventions", "Conventions"),
        ("23-glossary", "Glossary"),
    ]),
]

INLINE_CODE = re.compile(r"`([^`]+)`")
# ⚠ <b>IMAGE 는 반드시 LINK 보다 먼저 잡는다.</b> 뒤에 두면 `![alt](x.png)` 의 `[alt](x.png)` 를
#    LINK 가 먼저 먹어 `!` 한 글자 + 링크로 갈린다 — 이미지가 아니라 깨진 링크가 된다.
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
# ⚠ <b>굵게 안에 기울임이 들어갈 수 있어야 한다.</b> 종전 판은 `[^*]+` 이라 별표를 하나도 못
#    넘어서, `**… did *not* … **` 처럼 안에 기울임을 낀 문단이 통째로 안 풀리고 `**` 가 날것으로
#    남았다 (2026-09-17 · 10-dev-request 를 쓰던 세션이 밟았다). 부정 전방탐색은 `**` 만 막고
#    홑별표는 통과시킨다 — 28쪽 전부에서 결과가 한 바이트도 안 바뀌는 것을 확인하고 바꿨다.
BOLD = re.compile(r"\*\*((?:(?!\*\*).)+)\*\*")
ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")


def inline(text: str) -> str:
    """인라인 문법을 푼다. 코드 조각은 먼저 뽑아 두어 그 안이 다시 안 풀리게 한다."""
    slots: list[str] = []

    def stash(match: re.Match[str]) -> str:
        slots.append("<code>" + html.escape(match.group(1)) + "</code>")
        return "\x00%d\x00" % (len(slots) - 1)

    text = INLINE_CODE.sub(stash, text)
    text = html.escape(text, quote=False)
    text = IMAGE.sub(
        lambda m: '<img src="%s" alt="%s" loading="lazy">'
                  % (html.escape(m.group(2), quote=True), html.escape(m.group(1), quote=True)),
        text)
    text = LINK.sub(lambda m: '<a href="%s">%s</a>' % (html.escape(m.group(2), quote=True), m.group(1)), text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = ITALIC.sub(r"<em>\1</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], text)
    return text


def slug(text: str) -> str:
    plain = re.sub(r"<[^>]+>", "", inline(text))
    plain = html.unescape(plain).strip().lower()
    plain = re.sub(r"[^\w가-힣 -]", "", plain)
    return re.sub(r"[ _]+", "-", plain).strip("-") or "section"


def render_cards(lines: list[str]) -> str:
    """```cards 블록 — 한 줄이 카드 하나다: 대상 | 제목 | 설명."""
    out = ['<div class="cards">']
    for line in lines:
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|")]
        href = parts[0]
        title = parts[1] if len(parts) > 1 else href
        desc = parts[2] if len(parts) > 2 else ""
        num = ""
        stem = href.split("/")[-1].split(".")[0]
        if "-" in stem and stem.split("-")[0].isdigit():
            num = stem.split("-")[0]
        out.append('<a class="card" href="%s">' % html.escape(href, quote=True))
        if num:
            out.append('<span class="card__num">%s</span>' % num)
        out.append('<span class="card__title">%s</span>' % inline(title))
        if desc:
            out.append('<span class="card__desc">%s</span>' % inline(desc))
        out.append("</a>")
    out.append("</div>")
    return "\n".join(out)


def render_table(rows: list[str]) -> str:
    def cells(row: str) -> list[str]:
        row = row.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [c.strip() for c in row.split("|")]

    head = cells(rows[0])
    body = [cells(r) for r in rows[2:]]
    out = ['<div class="table-wrap"><table>', "<thead><tr>"]
    out += ["<th>%s</th>" % inline(c) for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


MARKER = re.compile(r"^(?:[-*]|\d+\.)\s+")


def render_list(block: list[str]) -> str:
    """중첩 목록. 들여쓰기 두 칸이 한 단계다.

    ⚠ <b>이어지는 줄을 먼저 합친 뒤에 inline 을 부른다.</b> 줄마다 부르면 줄바꿈을 낀
    ``**굵게**`` 가 여는 줄과 닫는 줄로 갈려 <b>양쪽 다 안 풀린다</b>(git.md 에서 실측).
    표시가 없는 들여쓴 줄은 새 항목이 아니라 앞 항목의 이어지는 줄이다.
    """
    items: list[tuple[int, str, str]] = []  # (indent, tag, text)

    for raw in block:
        line = raw.strip()
        if not line:
            continue
        if items and not MARKER.match(line):
            indent, tag, text = items[-1]
            items[-1] = (indent, tag, text + " " + line)
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        tag = "ol" if re.match(r"^\d+\.\s", line) else "ul"
        items.append((indent, tag, MARKER.sub("", line)))

    out: list[str] = []
    stack: list[tuple[int, str]] = []

    for indent, tag, text in items:
        while stack and indent < stack[-1][0]:
            out.append("</li></%s>" % stack.pop()[1])
        if not stack or indent > stack[-1][0]:
            out.append("<%s>" % tag)
            stack.append((indent, tag))
        else:
            out.append("</li>")
        out.append("<li>%s" % inline(text))

    while stack:
        out.append("</li></%s>" % stack.pop()[1])
    return "\n".join(out)


def markdown(text: str) -> tuple[str, str]:
    """(제목, 본문 HTML) 을 돌려준다. 첫 `# ` 이 제목이고 본문에서는 뺀다."""
    lines = text.replace("\r\n", "\n").split("\n")
    title = ""
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            block: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            if lang == "cards":
                out.append(render_cards(block))
            else:
                cls = ' class="language-%s"' % html.escape(lang, quote=True) if lang else ""
                out.append("<pre><code%s>%s</code></pre>" % (cls, html.escape("\n".join(block))))
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            body = stripped[level:].strip()
            if level == 1 and not title:
                title = re.sub(r"<[^>]+>", "", inline(body))
                title = html.unescape(title)
                i += 1
                continue
            anchor = slug(body)
            link = '<a class="anchor" href="#%s" aria-hidden="true">#</a>' % anchor if level in (2, 3) else ""
            out.append('<h%d id="%s">%s%s</h%d>' % (level, anchor, inline(body), link, level))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            rows: list[str] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(render_table(rows))
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            _title, inner = markdown("\n".join(quote))
            out.append("<blockquote>%s</blockquote>" % inner)
            continue

        if re.match(r"^([-*]|\d+\.)\s+", stripped):
            block = []
            while i < n and (re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]) or (lines[i].startswith("  ") and lines[i].strip())):
                block.append(lines[i].rstrip())
                i += 1
            out.append(render_list(block))
            continue

        # ⚠ 한 줄이 통째로 이미지면 <figure> 로 낸다 — <p> 안에 <figure> 를 넣으면 잘못된 HTML 이라
        #    브라우저가 <p> 를 제멋대로 닫는다. 글 속에 낀 이미지는 inline() 이 <img> 로만 낸다.
        alone = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", stripped)
        if alone:
            caption = alone.group(1)
            out.append(
                '<figure><img src="%s" alt="%s" loading="lazy">%s</figure>'
                % (html.escape(alone.group(2), quote=True), html.escape(caption, quote=True),
                   ("<figcaption>%s</figcaption>" % inline(caption)) if caption else "")
            )
            i += 1
            continue

        para: list[str] = []
        while i < n and lines[i].strip() and not re.match(r"^\s*(#|```|\||>|[-*]\s|\d+\.\s|-{3,})", lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))

    return title, "\n".join(out)


def nav_html(current: str) -> str:
    out: list[str] = []
    for group, items in NAV:
        out.append('<div class="sidebar__group">')
        out.append('<p class="sidebar__label">%s</p>' % html.escape(group))
        out.append('<ul class="sidebar__list">')
        for stem, label in items:
            # ⛔ <b>사이드바에 파일 번호를 찍지 마라 (2026-09-17).</b> 번호는 <b>파일 이름</b>이지
            #    읽는 순서가 아니다 — 묶음이 순서다. 세로 목록에 번호를 나란히 찍으면 묶음 경계에서
            #    27→06 · 17→12 · 24→21 로 거꾸로 가는 것처럼 보여 <b>「정렬이 깨진 목록」으로 읽힌다.</b>
            #    (묶음 <b>안</b>에서는 언제나 오름차순이고, index 의 카드도 그렇다.)
            mark = ' aria-current="page"' if stem == current else ""
            out.append(
                '<li><a href="%s.html"%s><span>%s</span></a></li>'
                % (stem, mark, html.escape(label))
            )
        out.append("</ul></div>")
    return "\n".join(out)


def neighbours(current: str) -> tuple[tuple[str, str] | None, tuple[str, str] | None]:
    flat = [item for _, items in NAV for item in items]
    for index, (stem, label) in enumerate(flat):
        if stem == current:
            prev = flat[index - 1] if index > 0 else None
            nxt = flat[index + 1] if index + 1 < len(flat) else None
            return prev, nxt
    return None, None


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%237657ac'/%3E%3Ctext x='16' y='22' font-family='sans-serif' font-size='15' font-weight='bold' fill='white' text-anchor='middle'%3EA%3C/text%3E%3C/svg%3E">
<link rel="stylesheet" href="assets/adp.css">
<script src="assets/adp.js"></script>
</head>
<body>
<header class="topbar">
  <a class="topbar__brand" href="index.html"><span class="topbar__mark">ADP</span><span>Builder docs</span></a>
  <span class="topbar__crumb">{crumb}</span>
  <span class="topbar__spacer"></span>
  <button class="topbar__btn nav-toggle" data-nav-toggle aria-expanded="false">Menu</button>
  <button class="topbar__btn" data-theme-toggle title="Switch light / dark">Theme</button>
</header>
<div class="layout">
  <nav class="sidebar" aria-label="Documentation">
    <input class="sidebar__search" data-nav-search type="search" placeholder="Filter pages…" aria-label="Filter pages">
    {nav}
  </nav>
  <main class="main">
    <article class="doc">
      <p class="doc__eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      {body}
    </article>
    <footer class="doc-footer">
      {prev}
      <span class="doc-footer__spacer"></span>
      <span class="pill">source: docs/adp/{stem}.md</span>
      {next}
    </footer>
  </main>
</div>
</body>
</html>
"""


def build(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    title, body = markdown(raw)
    stem = path.stem
    eyebrow = "ADP Builder reference"
    for group, items in NAV:
        for item_stem, _label in items:
            if item_stem == stem:
                eyebrow = group
    description = ""
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith(">"):
            description = re.sub(r"<[^>]+>", "", inline(line.lstrip(">").strip()))
            description = html.unescape(description)[:180]
            break
    prev, nxt = neighbours(stem)
    # 제목이 이미 제품 이름을 품고 있으면 꼬리를 또 붙이지 않는다 — 「… · ADP Builder」가 두 번 난다.
    page_title = title or stem
    return PAGE.format(
        page_title=html.escape(page_title if "ADP" in page_title else page_title + " · ADP Builder"),
        title=html.escape(title or stem),
        description=html.escape(description or "we-adk-builder reference documentation.", quote=True),
        crumb=html.escape(title or stem),
        eyebrow=html.escape(eyebrow),
        nav=nav_html(stem),
        body=body,
        stem=html.escape(stem),
        prev=('<a href="%s.html">← %s</a>' % (prev[0], html.escape(prev[1]))) if prev else "",
        next=('<a href="%s.html">%s →</a>' % (nxt[0], html.escape(nxt[1]))) if nxt else "",
    )


#: 본문에서 <code> 안을 걷어내는 그물. 린트가 반드시 이것을 먼저 거친다.
CODE_SPAN = re.compile(r"<code[^>]*>.*?</code>", re.S)
ARTICLE = re.compile(r'<article class="doc">(.*?)</article>', re.S)


def lint(pages: dict[str, str]) -> list[str]:
    """구운 html 이 제대로 섰나 — 안 풀린 마크다운 · 깨진 링크 · 태그 불균형 · NAV 밖.

    ⛔ <b>``**`` 를 생판 html 에 대고 훑지 마라 — 오탐이 일곱 쪽 난다.</b> 전부 {@code <code>} 안이고
    전부 정상이다: 인터셉터 경로 글롭({@code /projects/**} · {@code /**}) · 미리보기 경로
    ({@code …/files/**}) · 가림 결과({@code ://***@}) · Javadoc 여는 표시({@code /**}).
    <b>그것을 「안 풀린 마크다운」으로 보고 고치면 경로와 Javadoc 이 깨진다.</b>
    그래서 여기서 재기 전에 {@link CODE_SPAN} 으로 코드 안을 먼저 걷어낸다
    (2026-09-17 에 세 세션이 같은 오탐을 따로 밟고 확인한 자리다).

    ⚠ <b>그리고 「지적 0건」이 링크가 성하다는 뜻이던 적이 있다 — 아니었다.</b> 첫 판의 링크 검사는
    {@code href="…\\.html"} 만 봐서 확장자가 다른 죽은 링크를 통째로 놓쳤다
    (2026-09-17 · {@code git.md:256} → 지워진 {@code group-management.md}). 0 을 내는 동안 그 링크는
    죽어 있었고 <b>기계가 아니라 사람이 찾아냈다.</b> 오탐은 시끄러워서 드러나지만
    <b>미탐은 조용해서 안 드러난다</b> — 그물을 좁힐 때는 무엇이 빠져나가나를 먼저 세라.
    """
    problems: list[str] = []
    names = set(pages)
    in_nav = {stem for _group, items in NAV for stem, _label in items}

    for name, page in sorted(pages.items()):
        found = ARTICLE.search(page)
        body = found.group(1) if found else ""
        prose = CODE_SPAN.sub("", body)

        if "**" in prose:
            problems.append("%s: 안 풀린 굵게(**) — <code> 밖이다" % name)
        if re.search(r"^\|", body, re.M):
            problems.append("%s: 표로 안 선 줄(|)" % name)
        if body.count("<h1") != 1:
            problems.append("%s: h1 이 %d 개다" % (name, body.count("<h1")))

        for tag in ("ul", "ol", "li", "table", "blockquote", "pre", "div"):
            opened = len(re.findall(r"<%s[ >]" % tag, body))
            closed = len(re.findall(r"</%s>" % tag, body))
            if opened != closed:
                problems.append("%s: <%s> 짝이 안 맞는다 (%d/%d)" % (name, tag, opened, closed))

        # ⚠ <b>.html 만 재면 안 된다.</b> 종전 판이 그랬다가 {@code git.md} 의
        #    {@code (group-management.md)} 를 놓쳤다 — 지워진 파일을 가리키는데 확장자가 달라
        #    그물에 안 걸렸고, 사람이 손으로 찾아냈다 (2026-09-17). 이제 <b>모든 지역 링크</b>를 잰다.
        # ⚠ <b>href 만 훑으면 이미지가 통째로 빠져나간다.</b> 이 세트에서 같은 갈래의 미탐을
        #    이미 두 번 겪었다(`.html` 만 보던 링크 검사 · 죽은 `group-management.md`). 지워지거나
        #    이름이 바뀐 png 는 <b>조용히 깨진 아이콘</b>이 될 뿐 아무 데서도 안 터진다.
        for href in sorted(set(re.findall(r'(?:href|src)="([^"#:]+)(?:#[^"]*)?"', page))):
            if href.endswith(".html"):
                # ⚠ <b>구운 쪽만 아는 그물이었다.</b> 손으로 쓴 쪽(works-process/)은 디스크에 실재하는데도
                #    「없는 곳」으로 잡혔다. 파일 실존을 뒤에 대면 <b>죽은 링크는 그대로 걸리고</b>
                #    (그 파일이 없으니) 손으로 쓴 쪽만 통과한다 — 그물을 넓히는 것이지 푸는 것이 아니다.
                if href[:-5] not in names and not (ADP / href).exists():
                    problems.append("%s: 없는 곳으로 가는 링크 — %s" % (name, href))
            elif href.endswith(".md"):
                problems.append(
                    "%s: md 로 건 링크 — %s. 쪽끼리는 .html 로 건다" % (name, href))
            elif not (ADP / href).exists():
                problems.append("%s: 없는 파일로 가는 링크 — %s" % (name, href))

        if name not in in_nav and name != "README":
            problems.append("%s: NAV 에 없다 — 사이드바에 안 뜬다" % name)

    # ⚠ <b>반대쪽 썩음도 잰다.</b> 깨진 참조는 위에서 잡히지만, <b>아무도 안 가리키는 스크린샷</b>은
    #    조용히 남아 저장소만 불린다 — 쪽을 지우거나 이미지 줄을 뺐을 때 난다. 글과 달리 그림은
    #    코드에 대고 다시 잴 수 없으니, 적어도 <b>버려진 것</b>은 기계가 세게 해 둔다.
    shots = ADP / "assets" / "shots"
    if shots.is_dir():
        referenced = set()
        for page in pages.values():
            referenced.update(re.findall(r'src="([^"]+)"', page))
        for shot in sorted(shots.iterdir()):
            if shot.is_file() and ("assets/shots/" + shot.name) not in referenced:
                problems.append("assets/shots/%s: 아무 쪽도 안 가리킨다" % shot.name)

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="docs/adp 의 md 를 html 로 굽는다")
    parser.add_argument("--check", action="store_true", help="낡았으면 1 로 죽는다")
    parser.add_argument("--lint", action="store_true",
                        help="구운 판이 제대로 섰나 재고, 틀렸으면 1 로 죽는다")
    args = parser.parse_args()

    if args.lint:
        pages = {md.stem: build(md) for md in sorted(ADP.glob("*.md"))}
        problems = lint(pages)
        for problem in problems:
            print(problem)
        print("%d 쪽 · 지적 %d 건" % (len(pages), len(problems)))
        return 1 if problems else 0

    stale: list[str] = []
    made = 0
    for md in sorted(ADP.glob("*.md")):
        target = md.with_suffix(".html")
        fresh = build(md)
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != fresh:
                stale.append(target.name)
            continue
        target.write_text(fresh, encoding="utf-8", newline="\n")
        made += 1

    if args.check:
        if stale:
            print("낡았다: " + ", ".join(stale))
            return 1
        print("모든 html 이 md 와 같다")
        return 0

    print("%d 개 html 을 구웠다" % made)
    return 0


if __name__ == "__main__":
    sys.exit(main())
