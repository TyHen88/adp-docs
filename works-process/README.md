# docs/adp/works-process — process maps

> Twelve hand-drawn process maps — one action each, followed from the button a person presses to the
> last thing written to disk or sent over the network — plus the samples for exercising them.
> Open [`index.html`](index.html) to read them.

## These pages are hand-written, not generated

⛔ **`tools/build_html.py` does not own this folder.** The generator globs `*.md` in `docs/adp/`
only, so nothing here is built, checked or overwritten by it — and nothing here should be expected
to appear in the generated sidebar or in `NAV`.

That is the trade: the reference pages one level up are prose, generated from Markdown, and stay
consistent because a script writes them. These are diagrams, where the markup *is* the content, so
they are written by hand and kept in one folder that the script ignores.

```text
docs/adp/works-process/
├── index.html                the process map — start here
├── 01-project-setup.html     registering a planning repo and cloning it
├── 02-git-worktree.html      the clone, the worktrees, the four pushes
├── 05-frd-wizard.html        requirement → AI interview → confirmed scope
├── 06-frd-workbench.html     the drafting loop inside the worktree
├── 07-frd-completion.html    the completion run, the isolated merge, what it refuses to block on
├── 08-srt-fast-track.html    the short path, and the bridge FRD under it
├── 12-delivery-channel.html  the two transmission methods and how one request is bound to one
├── 03-send-to-dev.html       precheck → package → ZIP → POST → outcome
├── 14-dev-side.html          what DEVELOPER validates, shows and must return
├── 04-dev-result.html        polling, applying the result, merging to the default branch
├── 09-ai-run.html            how one `claude` run executes — underneath every page above
├── 10-green-zone.html        the three generated documents and the two development returns
├── 13-data-root.html         every folder under builder.data-root, and what nests inside
├── 11-frd-test-samples.html  five paste-ready requirement bodies for exercising FRD work
├── assets/flow.css           the diagram components; tokens come from ../assets/adp.css
└── README.md                 this file
```

⛔ **The number is a filename, not a reading order** — the same rule as the parent folder. The
sidebar is the reading order: setup → git → wizard → workbench → completion → SRT → channel → send → dev side → result,
then the three shared pages. `05`–`08` and `12` were filed after `01`–`04` and read in the middle, so the
numbers jump. Renumbering would rewrite every link in fifteen pages to fix an appearance.

The pages load `../assets/adp.css` and `../assets/adp.js`, so they follow the site's light/dark
theme and look like the rest of the documentation. `assets/flow.css` adds only the diagram
components (`.flow`, `.chain`, `.branch`, `.note`, `.tree`, `.panel`) and redefines no token.

## Reading the diagrams

| What you see | What it means |
|---|---|
| A numbered row | One ordered step: a git command, an HTTP call, or a state change |
| Grey text on the right | What that step costs you, or what it protects |
| Red text on the right | What happens when that step fails |
| A red callout | A trap that has already been hit at least once |
| A purple callout | A rule that must not be broken |

## Adding a page

1. Copy the closest existing page and keep the shell: the topbar, the sidebar list, `.doc.wp`,
   and the footer.
2. Add it to the sidebar list **in every page of this folder** — there is no generator to do it.
3. Add a card to `index.html`.
4. Link the reference page it expands on (`../04-project-setup.html`, `../git.html`,
   `../10-dev-request.html`, `../11-dev-result.html`), and name the classes it describes.

## What these pages are not

They are not a decision record, and they do not replace the reference pages. Where a process page
and a canonical source disagree, the canonical source wins: `CLAUDE.md`,
`docs/superpowers/specs/*.md`, `docs/developer-api-contract.md`, `docs/data-model.md`.

Language: English prose, with the Korean names kept wherever they appear in the code, the UI or the
domain (`FRD 작업하기`, `개발요청서`). The [glossary](../23-glossary.html) carries the mapping.
