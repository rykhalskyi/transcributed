# Project Wiki

Knowledge base in `wiki/`. Read `wiki/index.md` first; open pages only as needed.
Full conventions: [SCHEMA.md](SCHEMA.md).

## Rules

- Git is the change history — no `## Updates` sections, no dates in index entries.
- One page per work item: `pages/tickets/<ticket-id>-<brief>.md` with `## Spec`,
  `## Plan`, `## Outcome`.
- Separate `specs/`/`plans/` only for large epics shared by several tickets.
- Decisions are one-liners in `decisions.md` via the script; reference `D-nn`.
- Frontmatter: `created`, `type`, `status`, `summary` only.
- Never hand-edit `index.md`; regenerate it.
- Use relative markdown links, never wikilinks.

## Commands

```bash
node scripts/wiki.mjs index
node scripts/wiki.mjs lint
node scripts/wiki.mjs log <action> "<description>"
node scripts/wiki.mjs decision "<decision> — because <reason>"
```

Batch writes at the end of a session.
