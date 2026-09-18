# Design guide

> The visual rules of the target system, read from the derivatives the extractor bakes. A read-only window whose value is that it never disagrees with the index it came from.

Package: `com.bizplay.builder.design`
Screens: `artifacts/design-guide.html`
Routes: `/projects/{projectId}/artifacts/design-guide`
Canonical design: `docs/superpowers/specs/2026-09-10-design-guide-specimen-clipping-design.md`, `docs/serp-design-guide-findings.md`

## The one question it answers

**What are the visual rules of this business's source?**

The material is **two derivatives the extractor bakes**:

| Reader | Reads | Gives |
|---|---|---|
| `DesignIndexReader` | `design-index.json` | Colours, radii, typography, tokens |
| `StyleVocabularyReader` | `core/<system>/styleguide.md` | The class vocabulary |

## Two rules that define this screen

⛔ **Do not build an editing path.** These are derivatives: anything a human edits is destroyed at the next re-bake, and in the meantime the planning repository's checker raises `DESIGN-1` red.

⛔ **Do not read computed values.** The index does not follow `@import`, so there is no material from which to reconstruct the cascade winner. What this screen does is **list the declarations as they are** — and then what the screen says and what the index gave never differ by one character.

## The file name is not decided here

⛔ `DesignIndexReader` does not name the file. The location's source of truth is `manifest.json`'s `design-index` field, read by `PlanningManifestReader.designIndexFile` — the same discipline that keeps `iks` and `tnj` out of Builder's code.

⚠ **Missing or unreadable gives an empty value, not an exception.** Brand-new repositories and stale ones both exist, and neither may break a screen. The caller renders "not here yet". Same discipline as `PlanningManifestReader`.

## The style vocabulary is the interesting half

⭐ **The material for "the AI must not invent class names when writing a new screen" is `styleguide.md`, not `design-index.json`.**

The real `webview/styleguide.md` is 1,207 lines holding 1,150 classes — including the typo `ui-fex-1` that shipped in the source. **`ui-flex-1` does not exist in the source**, so writing it "correctly" produces a screen where not one line of style applies.

⚠ **Checker rule `A-5` reads the same fence.** A class outside this list turns the planning repository red — so this screen is where that red is seen in advance.

⛔ **Do not read outside the fence.** Outside it is an explanatory layer written by planners; treating that as the list promotes human prose into vocabulary. **No fence means the empty set**, not "everything".

## Curation

`DesignSystemCurationService` + `adk_builder_design_system_curation` store, **per project**, the meaning Builder has confirmed — without overwriting the extraction candidates.

Categories are a closed set: `button`, `text-field`, `textarea`, `select`, `checkbox`, `radio`, `switch`, `tabs`, `pagination`, `status`, `modal`, `table`, `upload`, `etc`. Component IDs must match `[A-Za-z0-9][A-Za-z0-9._-]{0,79}`.

Route: `POST …/design-guide/curation/{systemId}/components/{componentId}`.

## Serving the specimens

- `DesignGuideArtifactController` serves the extracted artifact files. Its URL pattern is one of the few **`permitAll`** paths, and is framed — see [Accounts & security](03-accounts-security.html).
- `DesignFrameController` provides the same-origin frame the specimens render in.
- `ShellFragmentReader` reads the shell fragment so a specimen can be clipped in context rather than shown bare.
- `DesignGuideArtifactAccess` and `DesignGuideCatalogReader` handle access checks and the catalogue.

## Related

- [Solution templates](13-solution-mockup.html) — the screens these rules describe
- [Spec checker](19-checker.html) — `DESIGN-1` and `A-5`
- [FRD workbench](07-frd-workbench.html) — where the design rules are applied on every edit
