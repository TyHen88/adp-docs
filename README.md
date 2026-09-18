# docs/adp — ADP Builder reference documentation

> A feature-by-feature reference for `we-adk-builder`, describing the system **as built**. Open [`index.html`](index.html) to read it.

## How this folder works

```text
docs/adp/
├── index.md / index.html      the hub — start here
├── NN-slug.md                 the source for one area (00–23)
├── NN-slug.html               generated from the .md of the same name
├── README.md                  this file
├── assets/adp.css             stylesheet; tokens mirrored from the product's tokens.css
├── assets/adp.js              theme toggle, mobile nav, sidebar filter
└── tools/build_html.py        the generator
```

**The Markdown is the source of truth. The HTML is generated.** Do not hand-edit an `.html` file here — the next build overwrites it.

```bash
python docs/adp/tools/build_html.py            # rebuild every page
python docs/adp/tools/build_html.py --check    # exit 1 if any HTML is stale
python docs/adp/tools/build_html.py --lint     # exit 1 if a baked page is malformed
```

`--lint` catches unparsed markdown, rows that did not become a table, broken internal links, unbalanced tags, and any page missing from `NAV`.

> ⛔ **Do not grep the generated HTML for `**` yourself.** Seven pages match and every one is correct — interceptor path globs (`/projects/**`, `/**`), a preview path (`…/files/**`), a masking result (`://***@`) and a Javadoc opener (`/**`). "Fixing" them breaks real paths. `--lint` strips `<code>` spans before measuring, which is why it reports zero.

The pages are plain files with relative links. Open `index.html` from disk; no server is needed.

## The number is a filename, not a reading order

⛔ **Do not renumber pages to make the sidebar ascend.** The number orders files on disk; **the group in `NAV` is the reading order.** Later pages were filed into the group they belong to, so numbers jump at group boundaries (`27` → `06`, `17` → `12`, `24` → `21`). Within any one group, and within each section of `index.md`, they always ascend.

The sidebar therefore prints **no number** — in a continuous vertical list a number reads as a position, and those jumps looked like a broken sort. Renumbering instead would mean rewriting 100+ cross-page links and breaking any outside reference, to fix an appearance.

## Adding a page

1. Write `NN-slug.md`. The first line is `# Title` (the only H1), and the blockquote directly under it becomes the page's meta description.
2. Add one `("NN-slug", "Short label")` entry to the right group in `NAV` in `tools/build_html.py`. That list is the source of truth for the sidebar and for the previous/next links.
3. Add a card to the matching section of `index.md`.
4. Run the build.

## Markdown the generator understands

Headings, paragraphs, tables, lists (nested by two-space indent, with wrapped continuation lines joined into the same item), fenced code blocks, blockquotes, horizontal rules, bold, italic, inline code and links. The renderer is small and dependency-free, so it knows only what this folder uses — in particular it handles **single** backticks only, so do not write a double-backtick span.

One extra: a ` ```cards ` fence renders a card grid, one card per line:

```text
target.html | Card title | One sentence of description
```

Link between pages with the `.html` name, so the links work in both the rendered site and a Markdown viewer that resolves siblings.

## What these documents are and are not

They **describe** the system. They are not its decision record. Where something is contested, the canonical sources are `CLAUDE.md`, `docs/artifacts.md`, `docs/data-model.md`, `docs/coding-conventions.md`, `docs/mockup-conventions.md` and `docs/superpowers/specs/*.md` — each page names the relevant one.

Language: English prose, with the Korean names kept wherever they appear in the code, the UI or the domain (`FRD 작업하기`, `개발요청서`, `그린존`). A name that appears on screen is never silently translated; the [glossary](23-glossary.html) carries the mapping.
