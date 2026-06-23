"""
SQLite layer for AIO Modeler.

Two first-class views over the same node graph:
- Architecture view (who-talks-to-whom)
- Phases view (timeline of orchestration)

Same nodes, different lenses.  Nodes carry placement hints for each view;
edges live in their own table because they're cheap and easy to query.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).parent / "modeler.sqlite3"


SCHEMA = """
CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id    INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,             -- stable id within board
    kind        TEXT NOT NULL,             -- agent | phase | artifact | tool | note
    name        TEXT NOT NULL,
    brief       TEXT,                      -- one-line tooltip
    body_md     TEXT,                      -- free-form markdown notes / extras
    meta_json   TEXT,                      -- structured fields (model, tools, system_prompt...)
    color       TEXT,                      -- hex for visual grouping
    arch_layer  INTEGER,                   -- legacy hint
    arch_col    INTEGER,                   -- legacy hint
    arch_x      INTEGER,                   -- canvas x (free-positioned arch view)
    arch_y      INTEGER,                   -- canvas y
    phase_order INTEGER,                   -- order in phases view (NULL = not a phase card)
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(board_id, key)
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id    INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    src_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    dst_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    label       TEXT,
    kind        TEXT DEFAULT 'comms',      -- comms | flow | reference
    order_idx   INTEGER                    -- chronological step number (NULL = unordered)
);

CREATE TABLE IF NOT EXISTS phase_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    order_idx     INTEGER NOT NULL,
    actor_node_id INTEGER REFERENCES nodes(id) ON DELETE SET NULL,
    action        TEXT NOT NULL,
    detail_md     TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_board       ON nodes(board_id);
CREATE INDEX IF NOT EXISTS idx_edges_board       ON edges(board_id);
CREATE INDEX IF NOT EXISTS idx_phase_steps_phase ON phase_steps(phase_node_id);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    """Auto-commit context manager. Rolls back on exception."""
    conn = connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    with cursor() as cur:
        cur.executescript(SCHEMA)
        # Lightweight migrations for DBs created before new columns existed.
        node_cols = {row["name"] for row in cur.execute("PRAGMA table_info(nodes)")}
        for col in ("arch_x", "arch_y"):
            if col not in node_cols:
                cur.execute(f"ALTER TABLE nodes ADD COLUMN {col} INTEGER")
        if "meta_json" not in node_cols:
            cur.execute("ALTER TABLE nodes ADD COLUMN meta_json TEXT")
        edge_cols = {row["name"] for row in cur.execute("PRAGMA table_info(edges)")}
        if "order_idx" not in edge_cols:
            cur.execute("ALTER TABLE edges ADD COLUMN order_idx INTEGER")


# ---------- query helpers (thin: keep app.py readable) ----------

def list_boards() -> list[sqlite3.Row]:
    with cursor() as cur:
        return cur.execute(
            "SELECT * FROM boards ORDER BY created_at DESC"
        ).fetchall()


def get_board(slug: str) -> sqlite3.Row | None:
    with cursor() as cur:
        return cur.execute(
            "SELECT * FROM boards WHERE slug = ?", (slug,)
        ).fetchone()


def get_board_by_id(board_id: int) -> sqlite3.Row | None:
    with cursor() as cur:
        return cur.execute(
            "SELECT * FROM boards WHERE id = ?", (board_id,)
        ).fetchone()


def nodes_for_arch(board_id: int) -> list[sqlite3.Row]:
    """Nodes visible in architecture view.  Returns rows ordered for stable rendering.

    A node appears on the arch canvas if EITHER arch_x is set (new free-position)
    OR arch_layer is set (legacy layered hint).  The view template prefers arch_x/y
    and falls back to deriving x/y from layer/col when arch_x is NULL."""
    with cursor() as cur:
        return cur.execute(
            """SELECT * FROM nodes
               WHERE board_id = ?
                 AND (arch_x IS NOT NULL OR arch_layer IS NOT NULL)
               ORDER BY arch_layer, arch_col, id""",
            (board_id,),
        ).fetchall()


def nodes_for_phases(board_id: int) -> list[sqlite3.Row]:
    """Phase-kind nodes in display order."""
    with cursor() as cur:
        return cur.execute(
            """SELECT * FROM nodes
               WHERE board_id = ? AND kind = 'phase' AND phase_order IS NOT NULL
               ORDER BY phase_order, id""",
            (board_id,),
        ).fetchall()


def get_node(node_id: int) -> sqlite3.Row | None:
    with cursor() as cur:
        return cur.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()


def edges_for_board(board_id: int) -> list[sqlite3.Row]:
    with cursor() as cur:
        return cur.execute(
            """SELECT * FROM edges WHERE board_id = ?
               ORDER BY COALESCE(order_idx, 9999), id""",
            (board_id,),
        ).fetchall()


def steps_for_phase(phase_node_id: int) -> list[sqlite3.Row]:
    with cursor() as cur:
        return cur.execute(
            """SELECT ps.*, n.name AS actor_name, n.color AS actor_color
                 FROM phase_steps ps
                 LEFT JOIN nodes n ON n.id = ps.actor_node_id
                WHERE ps.phase_node_id = ?
                ORDER BY ps.order_idx""",
            (phase_node_id,),
        ).fetchall()


def update_node_body(node_id: int, name: str, brief: str, body_md: str,
                     meta_json: str | None = None) -> None:
    with cursor() as cur:
        if meta_json is None:
            cur.execute(
                """UPDATE nodes SET name=?, brief=?, body_md=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?""",
                (name, brief, body_md, node_id),
            )
        else:
            cur.execute(
                """UPDATE nodes SET name=?, brief=?, body_md=?, meta_json=?,
                          updated_at=CURRENT_TIMESTAMP
                    WHERE id=?""",
                (name, brief, body_md, meta_json, node_id),
            )


def update_node_position(node_id: int, x: int, y: int) -> None:
    """Persist drag-drop position on the architecture canvas."""
    with cursor() as cur:
        cur.execute(
            "UPDATE nodes SET arch_x = ?, arch_y = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(x), int(y), node_id),
        )


def create_board(slug: str, name: str, description: str = "") -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO boards (slug, name, description) VALUES (?, ?, ?)",
            (slug, name, description),
        )
        return cur.lastrowid


def insert_node(board_id: int, **kw: Any) -> int:
    """Convenience for seed.py.  Accepts any subset of node columns."""
    cols = ["board_id"] + list(kw.keys())
    placeholders = ", ".join("?" for _ in cols)
    values = [board_id] + list(kw.values())
    with cursor() as cur:
        cur.execute(
            f"INSERT INTO nodes ({', '.join(cols)}) VALUES ({placeholders})",
            values,
        )
        return cur.lastrowid


def insert_edge(board_id: int, src_id: int, dst_id: int,
                label: str = "", kind: str = "comms",
                order_idx: int | None = None) -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO edges (board_id, src_id, dst_id, label, kind, order_idx)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (board_id, src_id, dst_id, label, kind, order_idx),
        )
        return cur.lastrowid


def insert_phase_step(phase_node_id: int, order_idx: int,
                      action: str, actor_node_id: int | None = None,
                      detail_md: str = "") -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO phase_steps
               (phase_node_id, order_idx, actor_node_id, action, detail_md)
               VALUES (?, ?, ?, ?, ?)""",
            (phase_node_id, order_idx, actor_node_id, action, detail_md),
        )
        return cur.lastrowid
