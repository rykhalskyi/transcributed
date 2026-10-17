---
created: 2026-10-17
type: overview
summary: Wiki structure, frontmatter, linking, slug, and workflow conventions.
---

# Wiki Schema

Read this only when you need the full conventions. The short version is in
[AGENTS.md](AGENTS.md).

## Token discipline

1. **Git is the history.** No `## Updates` sections, no "Created <date>" in index
   entries, no restating superseded content. Use `git log -p wiki/pages/<file>`.
2. **One page per work item by default.** A ticket page carries `## Spec`, `## Plan`,
   and `## Outcome`. Separate `specs/` + `plans/` pages only for large/ambiguous
   epics shared by many tickets.
3. **Decisions get a one-liner** in `decisions.md`; reference the id (`D-07`) from
   the ticket instead of restating rationale.
4. **Minimal frontmatter:** `created`, `type`, `status`, `summary`. No `tags`, no
   `related`.
5. **Never hand-edit `index.md`.** Regenerate with `node scripts/wiki.mjs index`.
   Append `log.md` / `decisions.md` with the script.
6. **`AGENTS.md` stays short**; detail lives here.
7. **Batch writes** at the end of a work session.

## Layout

```
wiki/
├── AGENTS.md      # short, always-loaded summary
├── SCHEMA.md      # this file
├── index.md       # generated catalog — never edit by hand
├── log.md         # append-only activity log
├── decisions.md   # append-only decision record (ADR-lite)
└── pages/
    ├── project-overview.md
    ├── build-deploy.md
    ├── debugging.md          # optional
    ├── epics/                # optional
    ├── tickets/              # default artifact per work item
    ├── specs/                # large/ambiguous epics only
    ├── plans/                # large/ambiguous epics only
    └── research/             # investigations and analysis
```

Helper script: `scripts/wiki.mjs` (args: `index`, `lint`, `log`, `decision`).

## Frontmatter

```yaml
---
created: YYYY-MM-DD
type: overview | build-deploy | epic | ticket | spec | plan | research
status: proposed | in-progress | implemented | superseded   # when meaningful
summary: One-line description used to build index.md
---
```

- `created` never changes after creation.
- `summary` is required on new pages so `index` can catalog without reading the body.
- Do not add `tags` or `related`. Legacy pages may keep them; leave them alone.

## Links

Relative markdown links only — never wikilinks. Paths are relative to the file
containing the link.

| From | To | Link |
|---|---|---|
| `wiki/index.md` | any page | `pages/<folder>/<slug>.md` |
| `pages/<sub>/x.md` | `pages/<other>/y.md` | `../<other>/y.md` |
| `pages/<sub>/x.md` | `pages/root-page.md` | `../root-page.md` |
| `pages/root-page.md` | `pages/<folder>/y.md` | `<folder>/y.md` |

## Slugs

- Tickets: `<ticket-id>-<brief>` (e.g. `ticket-15-localization-infra`, or
  `issue-11-dual-price` when sourced from a GitHub issue). Brief = 2-4 words,
  lowercase, hyphen-separated.
- Specs and plans share one `<feature-slug>` so they cross-link.
- Research: `<topic>`, lowercase, hyphen-separated.

## Workflow

### Default: one page per work item

```markdown
# T<n> — <Title>

Part of the [epic](../epics/<slug>.md).   # if applicable

## Spec
What and why: requirements, scope, design decisions, constraints.

## Plan
Ordered steps, files to create/modify, migrations, tests, risks.

## Outcome
What actually shipped, deviations from the plan, files changed.
```

Flip `status:` from `in-progress` to `implemented` when done.

### Large epic: optional spec + plan

Only when the work is genuinely large/ambiguous, or one spec is shared by several
tickets, create `pages/specs/<slug>.md` and `pages/plans/<slug>.md` and link the
ticket(s) to them.

## Operations

- **Ticket:** create `pages/tickets/<slug>.md`, fill the three sections, run
  `wiki.mjs index`, then `wiki.mjs log ticket "<title>"`.
- **Spec/Plan:** create pages under `pages/specs/` / `pages/plans/`, cross-link, run
  `index`, log with `wiki.mjs log spec|plan "<name>"`.
- **Research:** create `pages/research/<slug>.md` (context, findings, conclusions,
  recommended actions), run `index`, log with `wiki.mjs log research "<topic>"`.
- **Decision:** `node scripts/wiki.mjs decision "<decision> — because <reason>"`
  appends `- [YYYY-MM-DD] D-nn — <decision> — because <reason>` to `decisions.md`.
- **Index:** `node scripts/wiki.mjs index`.
- **Log:** `node scripts/wiki.mjs log <action> "<description>"`; actions: `init`,
  `ticket`, `spec`, `plan`, `research`, `update`, `decision`.
- **Lint:** `node scripts/wiki.mjs lint` checks missing `created`/`type`, dangling
  relative links, and pages missing from the index.
- **Query:** read `index.md` first, drill into pages, answer with relative links.
- **Update:** edit the page directly; regenerate the index if the summary changed;
  log with `wiki.mjs log update "<page> — <brief note>"`.

## Migration from `.design-specs` / `.opencode/plans`

When present: move `.design-specs/specs/*` to `pages/specs/<slug>.md` (use file
mtime as `created`), move `.opencode/plans/*` to `pages/plans/<slug>.md`, run
`index`, log each migration. Do not delete originals unless explicitly asked.
