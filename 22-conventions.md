# Conventions

> The rules this repository actually enforces: naming, screen work, testing effort, documentation, and the traps that have already cost time more than once.

Canonical documents: `docs/coding-conventions.md`, `docs/mockup-conventions.md`, `docs/data-model.md`, `CLAUDE.md`

## The one naming law

> **Names the machine calls are English. Words spoken to a person are Korean.**

This is not a new principle — `data-model.md` §0 already set it for the database ("column names in English snake_case", "meaning in a Korean `COMMENT`, written in detail"). The same law is extended to Java and to the screens. One rule means there is nowhere for two rules to disagree.

⚠ **This is not a rule to reduce Korean.** Writing explanations in detailed Korean is the house style and **stays**. Only the *called names* change.

| Place | Form | Example |
|---|---|---|
| Class / interface / enum / record | English PascalCase | `DocumentReadCheck`, `ReadVerdict` |
| Method | English camelCase | `register(...)`, `canRead()` |
| Field / local / parameter | English camelCase | `documentType` |
| Enum constant, constant | English SCREAMING_SNAKE_CASE | `MEETING_MINUTES`, `MIN_TEXT_RATIO` |
| View model key, fragment argument | English camelCase | `${title}`, `layout(title, shape, current, content)` |
| DB table / column | English snake_case, `adk_builder_` prefix | `adk_builder_received_document.preparation_state` |
| URL path, query name | English kebab-case | `/artifacts/received-docs` |
| Form field `name` | English camelCase | `name="documentType"` |
| **Comments / Javadoc** | **Korean** | `/** 올린 파일에서 글자가 실제로 나오나를 잰다. */` |
| **DB `COMMENT`** | **Korean** | |
| **Test method names** | **Korean** | `void 못_읽는_파일도_등록은_되고_상세에_까닭이_뜬다()` |
| **On-screen text** | **Korean** | `문서 등록`, `처리 대기` |
| **Exception messages, logs** | **Korean** | `throw new IllegalArgumentException("문서명을 입력해 주세요.")` |
| **Commit messages, documents** | **Korean** | |

⚠ **A test method name is a Korean sentence on purpose** — it is not a name anyone calls, it is a statement of **what is guaranteed**.

## Vocabulary

⛔ **Do not use 과업.** The general noun is **작업**. Three exceptions:

1. Describing the past ("종전에는 과업이…")
2. The name of a document received from outside (`과업요청서`)
3. Quoting another spec's wording in order to compare against it — the extractor spec's `과업ID` and `과업 축`. Renaming those would make comparison impossible.

## Screen work

**Before creating or changing any screen — mockup or template — read `docs/mockup-conventions.md` first.** It holds the screen composition, what to build with, UX copy, accessibility and the shared-shell verification rules.

- **The mockup is the source of truth for a screen.** Where it disagrees with a design document, the mockup wins. Editing a mockup is deciding the product, not editing a document.
- **One HTML renders one real product state.** Filled, empty, error and loading states do not appear together on one screen.
- **Do not put design notes into the product screen** as visible elements. Reasons go in the document or an HTML comment.
- **Do not mix a list and a workbench in one screen.** Layers are for simple confirmation; registration and editing with many fields, or needing original-text comparison, get their own screen.
- Default hierarchy: `title and main action → one sentence of purpose → search/filter → table or body`.
- ⛔ **Before inventing a new CSS class, look for whether the thing already exists.** Mockups and templates share a stylesheet.
- ⛔ **Changing the menu means changing `ShellContract.java`, `fragments/parts.html` and `_shell.js` together.** `ShellContractTest` fails if they drift. The mockups' `_shell.js` is a copy — never write the order from memory; read the `nav` fragment in `parts.html`.

## Verification is proportional to risk

**Running more is not itself quality.**

| Change | Verification |
|---|---|
| **Pure design change** — wording, button names and positions, spacing, colour, HTML/CSS arrangement, with no routing, conditional, view model or server behaviour touched | `git diff --check` + look at the changed screen at desktop and 375px + `check_mockups.py` if a mockup changed. **No full Maven run, no separate broad review.** |
| **Thymeleaf conditionals, form values, permission exposure, DOM contract** | Only the test classes that cover that contract |
| **Java behaviour, routing, DB, security, shared shell** | Start from the related tests; widen to `./mvnw test` only when the blast radius is wide |

Pre-existing unrelated failures are **not** chased down in this work — confirm as much as needed and report.

⚠️ **"Fast" is bought by narrowing feature scope, not by verifying less.** Logic changes do not get shallow tests, and TDD applies to features and bug fixes as before.

**The finish line for a feature or logic change is a green `./mvnw test`.** Whether the screen actually renders is checked by a human — that is the boundary between what a machine measures and what a person sees.

## Migrations and the ERD

Measure the next number **immediately before creating the file**:

```bash
ls src/main/resources/db/migration/ | sed 's/__.*//' | sort -V | tail -1
```

⛔ Never write a migration number into a document or plan. ⛔ Never edit an applied migration. ⛔ Redraw the ERD before committing:

```bash
python docs/tools/erd_from_migrations.py
```

Full detail, including the six times this was got wrong, is in [Data model](02-data-model.html).

## Documentation

- **One document = one question.** The question goes at the top as a blockquote.
- **Unresolved items do not go in the body — they go to a GitHub issue.** Previously 510 markers (one every 13 lines) rotted inside the documents.
- **500 lines is an alarm, not a limit.** Past it, look for the question to split out.
- ⛔ **Do not reference another repository's `§section`.** Copy the text instead. References are what grew the previous 15 documents to 6,695 lines.
- ⛔ **Do not write artifact counts into the shared topology block.** "12 artifacts" becoming 14 is where the extractor and Builder actually diverged — the extractor dropped the count first and Builder followed late. The canonical count lives in `docs/artifacts.md` alone.

### Measure *what is* from code; take *why* from the design documents

A design document goes stale in one direction only, and knowing which direction saves re-deriving it:

| Kind of claim | Source of truth | Why |
|---|---|---|
| **What is the case** — input fields, how many values an enum has, which route runs, what a constraint enforces | **The code, and the DB for schema** | This is what drifts. The document was written before the code settled |
| **Why it was decided** | **The design document** — it is the *only* source | Reasons are not in the code, and once lost they are unrecoverable |

⛔ **Never cite a design document for a fact about current behaviour.** Measured twice in one session, both times wrong in the same direction:

| Claim taken from a document | What the code does |
|---|---|
| `README.md`: the account name and email become the git commit author | Every commit hardcodes `user.name=Builder`; no git call reads the account |
| SRT spec: Flow registration accepts "a task number **or a URL**" | `SrtService.registerFlow` enforces `^[0-9]+$` — a URL is rejected |

⛔ And the converse: **do not try to reconstruct a reason from the code.** The 2026-09-02 decision that moved "a simple change to one existing screen" out of the FRD fast track exists in exactly one place — line 11 of `2026-08-18-frd-fast-track-design.md`. No amount of reading `SrtService` recovers it.

## Traps that have already cost time

| Trap | What happens |
|---|---|
| `@Async` called from the same class | The proxy is skipped and it runs **on the request thread** — six minutes on `nio-8080-exec-2` in production |
| Instruction placed last on the `claude` command line | Swallowed by a multi-value flag; the prompt vanishes entirely |
| Reading one process stream to completion first | Deadlock on a full pipe, and the timeout stops meaning anything |
| Leaving `claude`'s stdin open | Three seconds lost on **every** run |
| Editing an applied migration | Flyway refuses to start |
| An untracked migration file | Invisible to `git log`, `git status` and the worktree; visible only to `ls`. Flyway rejects the whole context at runtime |
| A wrong `ShellContract` argument | Not a 500 — a normal-looking page with the menu and project name missing |
| Checking inside the shared clone | Two simultaneous saves mix drafts and the before/after verdict becomes false |

## Related

- [Architecture](01-architecture.html) — the patterns these rules protect
- [Data model](02-data-model.html) — migration and ERD rules in full
- [Glossary](23-glossary.html) — the Korean terms used throughout
