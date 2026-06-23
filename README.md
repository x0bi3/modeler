# AIO Modeler

A Miro-but-honest design tool for sketching agent orchestration systems.
Single-user, runs locally, SQLite under the hood.

## Why this exists

When you're designing an agentic system with 5-15 agents, long system
prompts, JSON schemas, and a flow of artifacts between them — Miro feels
heavy and Notion feels flat.  This is a thin, focused tool with **two
views over the same data**:

- **Architecture view** — who talks to whom (layered diagram with SVG edges)
- **Phases view** — what happens in order (timeline with steps per phase)

Click any node to slide in a side panel with the **full Markdown content**
(system prompt, tool list, schema, notes).  Edit in place.

## Run

```
run-modeler.bat
```

Opens at http://127.0.0.1:8767/.  On first boot it auto-seeds the example
board (`/b/aio-orchestrator`) which models Ryan's Intent Clarifier ->
Orchestrator -> Judge -> Sub-Agent concept.

## Stack

- FastAPI + Jinja2 + HTMX  (no SPA framework)
- Tailwind v4 (browser JIT, vendored)
- Marked.js for markdown rendering (vendored)
- SQLite (single file `modeler.sqlite3`)

All assets are vendored under `static/` so it works without internet.

## Re-seeding

```
.venv\Scripts\python.exe seed.py
```

or `POST /admin/reseed` while the server is running.  Drops and rebuilds
the `aio-orchestrator` board only — your other boards are untouched.

## Adding a new board

`/` -> "+ New board" -> pick a slug + name.  Empty board, ready to add
nodes (right now via direct DB writes; node CRUD UI is the obvious next
feature).

## File layout

```
app.py        FastAPI routes (pages + HTMX partials)
db.py         SQLite schema + query helpers
seed.py       Example "AIO Orchestrator" board content
templates/    Jinja2 templates (base + page + partials)
static/       Vendored JS (tailwind, htmx, marked)
```

## What's NOT here (yet)

- Drag-to-position nodes on the architecture view
- Node CRUD UI (only edits to existing nodes work in v1)
- Edge editing UI
- Export to JSON / import from JSON
- Multi-user / auth (it's a single-user local tool)
