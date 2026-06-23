"""
AIO Modeler -- a Miro-but-honest design tool for sketching agent orchestration.

Two synchronized views of the same node graph:
- /b/<slug>            -> Architecture view (who-talks-to-whom)
- /b/<slug>/phases     -> Phases view (timeline of orchestration)

Drill-down: click any node -> HTMX side panel slides in with full markdown.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db

ROOT = Path(__file__).parent
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def lifespan_setup() -> None:
    """Ensure schema exists on every boot.  Seed only if no boards yet."""
    db.init_schema()
    if not db.list_boards():
        import seed
        seed.seed()


lifespan_setup()

app = FastAPI(title="AIO Modeler")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


def _no_cache(resp: Response) -> Response:
    """Templates change often during a design session; never cache HTML."""
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _parse_meta(raw: str | None) -> dict[str, Any] | None:
    """Best-effort decode of nodes.meta_json.  Returns None for non-agent nodes
    or anything that doesn't parse."""
    if not raw:
        return None
    try:
        meta = json.loads(raw)
        return meta if isinstance(meta, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _tools_from_text(text: str) -> list[dict[str, str]]:
    """Parse the edit-form tools textarea.  One tool per line, format:

        Tool_A | what it does
        Tool_B | what it does

    Empty lines and lines without a pipe are skipped (or treated as
    purpose-less).  Returns a list of {name, purpose} dicts."""
    tools: list[dict[str, str]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            name, _, purpose = line.partition("|")
            tools.append({"name": name.strip(), "purpose": purpose.strip()})
        else:
            tools.append({"name": line, "purpose": ""})
    return tools


def _node_with_meta(node_id: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Fetch a node and its parsed meta dict (None if not present)."""
    row = db.get_node(node_id)
    if not row:
        raise HTTPException(404, "node not found")
    node = dict(row)
    meta = _parse_meta(node.get("meta_json"))
    # Only present the meta editor for agent-kind nodes.  Artifacts use the
    # simple body_md textarea.
    if node.get("kind") != "agent":
        meta = None
    # For agent nodes with no meta yet, give the edit form blank scaffolding
    # so the structured editor still shows up.
    if node.get("kind") == "agent" and meta is None:
        meta = {"model": "", "system_prompt": "", "tools": [],
                "output_schema": "", "notes_md": ""}
    return node, meta


# ============================================================
# Pages
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Response:
    return _no_cache(templates.TemplateResponse(
        request, "boards.html", {"boards": db.list_boards()}
    ))


@app.post("/boards/new")
async def create_board(slug: str = Form(...), name: str = Form(...),
                       description: str = Form("")) -> RedirectResponse:
    slug = slug.strip().lower()
    if not SLUG_RE.match(slug):
        raise HTTPException(400, "slug must be lowercase, alphanumeric + hyphens")
    if db.get_board(slug):
        raise HTTPException(409, f"board '{slug}' already exists")
    db.create_board(slug, name.strip(), description.strip())
    return RedirectResponse(f"/b/{slug}", status_code=303)


@app.get("/b/{slug}", response_class=HTMLResponse)
async def board_arch(request: Request, slug: str) -> Response:
    board = db.get_board(slug)
    if not board:
        raise HTTPException(404, f"no board '{slug}'")
    nodes = [dict(n) for n in db.nodes_for_arch(board["id"])]
    for n in nodes:
        if n.get("arch_x") is None:
            n["arch_x"] = 180 + 380 * (n.get("arch_col") or 0)
        if n.get("arch_y") is None:
            n["arch_y"] = 40 + 160 * (n.get("arch_layer") or 0)
    edges = [dict(e) for e in db.edges_for_board(board["id"])]
    return _no_cache(templates.TemplateResponse(
        request, "board.html",
        {"board": dict(board), "view": "arch", "nodes": nodes, "edges": edges},
    ))


@app.get("/b/{slug}/phases", response_class=HTMLResponse)
async def board_phases(request: Request, slug: str) -> Response:
    board = db.get_board(slug)
    if not board:
        raise HTTPException(404, f"no board '{slug}'")
    phases = [dict(p) for p in db.nodes_for_phases(board["id"])]
    for p in phases:
        p["steps"] = [dict(s) for s in db.steps_for_phase(p["id"])]
    return _no_cache(templates.TemplateResponse(
        request, "board.html",
        {"board": dict(board), "view": "phases", "phases": phases},
    ))


# ============================================================
# HTMX partials -- drill-down side panel
# ============================================================

@app.get("/node/{node_id}/panel", response_class=HTMLResponse)
async def node_panel(request: Request, node_id: int) -> Response:
    node, meta = _node_with_meta(node_id)
    # In view mode, only show meta if there's actually content in it.  An
    # empty-scaffold meta would otherwise render a bunch of empty sections.
    view_meta = meta if (meta and any(meta.get(k) for k in
        ("model", "system_prompt", "tools", "output_schema", "notes_md"))) else None
    return _no_cache(templates.TemplateResponse(
        request, "_panel.html",
        {"node": node, "meta": view_meta, "mode": "view"},
    ))


@app.get("/node/{node_id}/edit", response_class=HTMLResponse)
async def node_panel_edit(request: Request, node_id: int) -> Response:
    node, meta = _node_with_meta(node_id)
    return _no_cache(templates.TemplateResponse(
        request, "_panel.html",
        {"node": node, "meta": meta, "mode": "edit"},
    ))


@app.post("/node/{node_id}", response_class=HTMLResponse)
async def node_save(
    request: Request, node_id: int,
    name: str = Form(...), brief: str = Form(""), body_md: str = Form(""),
    # Structured-editor fields (only present for agent nodes).  All optional
    # because artifact saves don't include them.
    meta_model: str | None = Form(None),
    meta_system_prompt: str | None = Form(None),
    meta_tools: str | None = Form(None),
    meta_output_schema: str | None = Form(None),
    meta_notes_md: str | None = Form(None),
) -> Response:
    node = db.get_node(node_id)
    if not node:
        raise HTTPException(404, "node not found")

    # If any structured field came through, rebuild meta_json from them.
    # Otherwise leave the existing meta_json untouched.
    meta_json_str: str | None = None
    if any(v is not None for v in (
        meta_model, meta_system_prompt, meta_tools,
        meta_output_schema, meta_notes_md,
    )):
        meta_json_str = json.dumps({
            "model":         (meta_model or "").strip(),
            "system_prompt": meta_system_prompt or "",
            "tools":         _tools_from_text(meta_tools or ""),
            "output_schema": meta_output_schema or "",
            "notes_md":      meta_notes_md or "",
        })

    db.update_node_body(node_id, name.strip(), brief.strip(), body_md, meta_json_str)
    return await node_panel(request, node_id)


@app.post("/node/{node_id}/position")
async def node_position(node_id: int, x: float = Form(...), y: float = Form(...)) -> dict:
    """Persist a drag-drop. Fire-and-forget from the client; tiny JSON ack."""
    if not db.get_node(node_id):
        raise HTTPException(404, "node not found")
    db.update_node_position(node_id, int(x), int(y))
    return {"ok": True, "x": int(x), "y": int(y)}


# ============================================================
# Dev convenience
# ============================================================

@app.post("/admin/reseed")
async def reseed() -> dict:
    """Drop & rebuild the example board.  POST only so it doesn't fire on F5."""
    import seed
    board_id = seed.seed()
    return {"ok": True, "board_id": board_id, "slug": "aio-orchestrator"}
