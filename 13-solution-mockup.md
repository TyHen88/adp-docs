# Solution templates

> The current production screens, extracted by the extractor. Where they are stored (not the database), how a repository update reaches them, the three sources each screen is assembled from, and the three-stage preview pipeline.

Package: `com.bizplay.builder.solution`
Screens: `artifacts/solution-mockups.html`, `artifacts/solution-mockup.html`
Routes: `/projects/{projectId}/artifacts/solution-mockups`, preview under `…/solution-mockups/files/**`
Canonical design: `docs/superpowers/specs/2026-08-22-preview-skin-design.md`, `2026-09-10-preview-shell-fill-design.md`, `2026-09-10-preview-width-design.md`

## What they are

**솔루션 템플릿 (solution templates)** are the current production screens as the extractor captured them. Builder never reads the production source itself — it reads the clone. Every link uses the planning repository's **screen ID** (`wv-card-list` shape).

⭐ **An FRD starts from the current solution template, not from the previous FRD's result.**

## Are they stored in the database?

**No. Never — not at clone time, not at repository update.**

There is no table for them. The only screen-shaped tables in the schema belong to other things:

| Table | What it is for |
|---|---|
| `adk_builder_frd_screen` (+ history, markers, memos, chat, IA placement) | Screens **inside an FRD's work**, not production screens |
| `adk_builder_ia_screen_profile` | Menu-tree profile data |
| `adk_builder_screen_standard_id`, `adk_builder_screen_id_group` | The standard-ID mapping |
| `adk_builder_screen_design*` | Generated screen-design documents |
| `adk_builder_mockup_mismatch` | Builder's "differs from production" flags |

Solution templates themselves live **only as files in the clone**, and are read on demand:

```text
<data-root>/projects/<projectId>/clone/
├── index.json                              ← screen catalogue
└── core/<system>/
    ├── pages/<screenId>.html               ← the mockup
    ├── pages/<screenId>.md                 ← the screen document
    ├── assets/                             ← css · js · images (all skins)
    └── shell.md                            ← markup for the shell slots
```

## So what does a clone or update actually write?

This is the precise answer to "does it insert into the DB, or at clone?" — **neither writes screens**, but both write *three other things*.

`CloneWorker` (first clone) and `RepositoryUpdateWorker` (later updates) both finish with the same three steps:

| Step | Writes to | What |
|---|---|---|
| `projects.cloneSucceeded` / `repositoryUpdateSucceeded` | `adk_builder_project` | State, and for updates the before/after `HEAD` SHA so it knows whether anything moved |
| `projectSystems.syncQuietly` | `adk_builder_project_system` | The repository may have gained or lost a system. Display names already entered are left alone |
| `screenIds.assignQuietly` | `adk_builder_screen_standard_id` | New screens get standard IDs. **Fills only what is missing**, so re-running costs nothing — and it doubles as a retry for a previous failed assignment |

Both of the last two are deliberately "quiet": ⛔ if they throw, the clone or update is **already a success** and the next run retries. A failure to assign an ID must not turn a good clone into a failed project.

The update path adds one guard the clone path cannot need — `merge --ff-only`, so an update that is not a clean fast-forward **does not happen at all** (see [architecture](01-architecture.html) and the fetch rules in [git layer](git.html)).

## How an update becomes visible

Since nothing is inserted, there is no "refresh the data" step. The mechanism is a **content stamp on an in-memory cache** in `SolutionScreenReader`:

```java
stamp = <git HEAD of the clone> + ":" + <index.json last-modified millis> + ":" + <facet list>
```

- Read a project's screens → if the cached snapshot's stamp matches, return it.
- A repository update moves `HEAD` → the stamp changes → the next read re-sweeps the clone.

⚠ **`HEAD` alone is not enough.** Someone editing the clone by hand can change `index.json` **without committing**, which really happens when people inspect a planning-repository clone. The file's modification time catches that.

The facet list is in the stamp because renaming a facet changes what the screens resolve to — see [project setup](04-project-setup.html).

So: **update the repository → the cache invalidates itself → the next page load shows the new screens.** No insert, no migration, no manual reindex.

## The three sources behind one screen

`SolutionScreenReader` assembles each `SolutionScreen` from three places (measured 2026-08-16, clone `9886e9c`, 274 screens):

| Source | What it gives |
|---|---|
| `index.json` | Screen ID · system · kind · screen type · type basis · institution variant |
| `core/<system>/pages/<screenId>.md` | Screen name and purpose (`--- 화면명세 ---`) · menu path · main functions · linked screens |
| `git log` | First written · last modified · who modified it · what changed |

The assembled record:

```java
record SolutionScreen(
    String screenId, String screenName, String summary,
    String system, String kind, String screenType, String typeSource,
    String menuPath, String iaPath,
    String facetCode, String facetName,
    List<SolutionVariant> variants, List<String> projectFacetNames,
    String parentScreenId, List<String> openingScreenIds,
    boolean shared, ScreenHistory history)
```

### The git history is swept once

⛔ **Never call `git log` per screen** — 274 screens would spawn 274 processes. One sweep with `--name-only` over `core`, then split by file, gives the same result at 1/274 of the cost:

```bash
git log --date=short --format=@@@%ad%x09%an%x09%s --name-only -- core
```

⚠ **If it fails, the map is empty and screens still render.** A shallow clone, or no git at all, must not blank the screen list.

⚠ Likewise, an unreadable `index.json` returns an empty list rather than throwing — the same discipline as `PlanningManifestReader`.

## The preview pipeline

`SolutionPreviewController` serves files under `/projects/*/artifacts/solution-mockups/files/**` and the detail screen embeds them in an `iframe`. An HTML file passes through **three stages, in this order**:

```text
read file
  → SkinRewriter.draw()      swap the institution skin folder in href/src
  → ShellSlotFiller.fill()   fill the slots the demo script used to fill
  → sanitizeHtml()           strip <script>
  → serve
```

Only whitelisted types are served at all: `html`, `css`, `js`, `png`, `jpg`, `jpeg`, `gif`, `svg` (`SERVABLE`).

### 1. Skin rewriting — `SkinRewriter`

⭐ **g2c's 252 webview screens share a single common mockup**, so without swapping at render time **there is no way to view them as 제주**.

The contract came from extractor reply #5, and the boundary is theirs: **markup differs → the extractor's job (variant mockups); only style differs → Builder's job (here).**

Three deterministic steps:

1. Resolve `href` and `src` **relative to the folder the mockup sits in**, producing repository-root-relative paths.
2. If that path falls under some institution's skin folder (boundary at `/`), replace that prefix with the chosen institution's folder.
3. Re-relativise against the mockup folder and write it back into the link.

⛔ **The stored copy is never modified — substitution happens in the response only.** That is `SkinRewriter`'s own contract, and it is why the [development request package](10-dev-request.html) ships *all* of `core/<system>/assets/` rather than selecting a skin: selecting would require rewriting links on a stored copy, and it would put `iks`/`tnj`-shaped strings into Builder's code.

⛔ **The institution → CSS folder mapping is business knowledge. Its single source is the clone's `manifest.json` → `systems[].skins`.** The moment Builder's code holds one of those folder names, Builder knows `g2c` — the boundary the whole rebuild exists to keep.

`PreviewFacets` decides which facet, and therefore which skin, the current preview uses.

### 2. Shell slot filling — `ShellSlotFiller`

Because scripts are stripped, the slots the mockup's demo script used to fill stay empty and the planner sees **a white strip with no icons**.

⭐ The markup for those slots **already arrives as `core/<system>/shell.md`** — nothing is invented.

⛔ **Do not guess which slots.** An earlier version located them by HTML sectioning elements (`<header>`, `<footer>`); measured across the whole set, **what was meant to fill eight filled a hundred and fifty** — including sub-headers whose own CSS already drew a title, and slots that **are legitimately empty in the source too**.

### 3. Script stripping — `sanitizeHtml`

The preview is not a running application; it is a picture of one. Stripping `<script>` also means the browser logs no blocked-script noise. The FRD screen and history previews go through the same fence.

Same-origin framing is granted to exactly this pattern and a few siblings — see [accounts & security](03-accounts-security.html).

## Mismatch flags — the one writable half

> ⚠ **The two halves of this screen have different natures.** The screens belong to the planning repository, so Builder only reads them. The flags belong to Builder, so Builder writes them. They appear side by side, but **only the flag is editable.**

`POST /{screenId}/mismatch` → `SolutionMockupService.report(...)` inserts into `adk_builder_mockup_mismatch`. A reason is required:

> "어디가 다른지 한 줄 적어야 표시할 수 있습니다." — *write one line saying what differs.*

This is a signal back to the extractor that the mockup does not match the real production screen. It is **not** a repair — Builder cannot fix the mockup, because it cannot read the production source.

## Who consumes solution templates

| Consumer | How |
|---|---|
| [FRD wizard](06-frd-wizard.html) | The interview picks target screens from this list |
| [FRD workbench](07-frd-workbench.html) | An AI draft starts from the as-is mockup |
| [Feature spec](16-green-zone.html) | `FeatureSpecMaterialService` goes through `SolutionMockupService` rather than re-reading the clone — ⛔ a second sweep would read the same 274 screens twice |
| [Development request](10-dev-request.html) | `as-is.html` in the package comes from here |
| [IA](12-ia.html) | The menu tree is built from the same index |

## Related

- [Project setup](04-project-setup.html) — clone, repository update, facets
- [Git layer](git.html) — fetch and `merge --ff-only` mechanics
- [Design guide](14-design-guide.html) — the visual rules these screens follow
- [Screen IDs](18-screen-id.html) — how they are identified
