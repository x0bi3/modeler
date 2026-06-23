"""
Seed the modeler with Ryan's AIO Orchestrator concept.

This file is the single source of truth for the example board.  Re-running
it drops and rebuilds the board so iterating is cheap.

Mental model:
- Architecture view = WHO talks to WHO (agents + key artifacts on a layered grid)
- Phases view      = WHAT happens, in order (Phase 1..4 with detailed steps)
- Every node has a 1-line brief (preview tooltip) and a body_md (drill-down)
"""

from __future__ import annotations

import db


# ----------------------------------------------------------------------
# Long-form content lives at module top so it's easy to edit without
# scrolling through the wiring code below.
# ----------------------------------------------------------------------

USER_BODY = """
# User

The human kicking off the workflow.  Provides:

- **Initial request** (often vague: *"build me a website"*)
- **Questionnaire answers** to the Intent Clarifier
- **Clarifications** to the Orchestrator when intent gaps surface
- **Approval / modifications / rejection** of the Judge's assessment

Communicates **only** with Intent Clarifier, Orchestrator, and Judge.
Never sees Sub-Agents directly — the Orchestrator brokers everything.
"""


INTENT_CLARIFIER_BODY = """
# Intent Clarifier — System Prompt

You are the **Intent Clarifier**.  Your job is to transform vague user
requests into structured information that the Orchestrator can use.

**Input:** Raw user request (likely incomplete, vague, or lacking detail)
**Output:** 5-10 contextual questions + collected answers, synthesized into
a **User Intent Summary**.

## Rules

1. Ask questions progressively — **not all at once**.  Wait for answers.
2. Questions are domain-specific (website → ask about design, hosting,
   audience; video → ask about length, platform, style).
3. Prioritize questions that unlock the most information early
   (e.g. *"What's your budget?"* unlocks scope).
4. Be conversational, not robotic.  Acknowledge each answer.
5. After all answers, synthesize a **User Intent Summary** containing:
   - Core request
   - Target audience / use case
   - Constraints (budget, timeline, tech stack)
   - Must-haves vs nice-to-haves
   - Success criteria

## Output Schema (JSON)

```json
{
  "raw_request": "...",
  "questionnaire": [{"q": "...", "a": "..."}, ...],
  "synthesized_intent": {
    "core_request": "...",
    "target_audience": "...",
    "scope": "...",
    "budget": "...",
    "timeline": "...",
    "must_haves": ["..."],
    "nice_to_haves": ["..."],
    "success_criteria": "...",
    "constraints": ["..."],
    "tech_hints": ["..."]
  }
}
```

## Example questionnaire (e-commerce site)

1. What product/service is the website for?
2. Who is your target customer?
3. What's your budget range?
4. Do you have existing branding (logo, colors, fonts)?
5. Timeline (ASAP, 2 weeks, 1 month, flexible)?
6. E-commerce or marketing only?
7. Domain/hosting already, or set up?
8. Tech preferences (WordPress, React, Shopify, ...)?
9. Ongoing maintenance needed?
10. Primary goal (sales / leads / brand awareness)?
"""


ORCHESTRATOR_BODY = """
# Orchestrator — System Prompt

You are the **Orchestrator Agent**, designed as a **Routing Agent**.
You manage multi-layer conversations between User, Orchestrator (you),
and the assigned Sub-Agents.

```
User  <->  Orchestrator (you)  <->  Sub-Agent Team
```

Sub-Agents **never** communicate with the User directly.

## Core principle

You **DO NOT execute actions**.  You do not carry out user requests.
Your only roles are:

1. **Intent Discovery** — fill the gaps the Intent Clarifier missed.
2. **Consult relevant Sub-Agents** — surface feasibility, risk, tech detail.
3. **Build & maintain the Task Plan** — assign work to Sub-Agents.
4. **Finalize the plan** for Judge review.

## Tools available to you

| Tool | Purpose |
|---|---|
| `Ask_User_Questions` | Gather more info, clarify intent |
| `Update_Plan`        | Add / modify / remove task plan items |
| `Get_Plan`           | Retrieve latest plan structure |
| `Consult_Sub_Agent`  | Start / resume conversation with a Sub-Agent |
| `Finalize_Plan`      | Ship the plan to the Judge for review |
| `Get_Sub_Agent_Summary` | Retrieve Sub-Agent scopes, tools, skills, resources |

## Sub-Agents (provided per session)

Each entry: name, specialty brief, tools schema, resources schema.

## Inputs at runtime

- **Current Task Plan** (starts empty)
- **User's Introductory Post** (the summarized intent from Phase 1)
"""


JUDGE_BODY = """
# Judge / Assessor — System Prompt

You are the **Judge/Assessor**.  Your role is **quality assurance** on
Task Plans before they hit execution.

## Inputs

- Task Plan from Orchestrator
- User Intent Summary
- Sub-Agent capabilities / constraints

## Assessment criteria

1. **Completeness** — covers all must-haves?  Any obvious gaps?
2. **Feasibility** — timeline realistic?  Budget OK?  Resources available?
3. **Risk** — what can go wrong?  Mitigation in place?
4. **Clarity** — success criteria measurable?  Deliverables well-defined?

## Verdicts

- `APPROVED`              — ship it
- `APPROVED_WITH_NOTES`   — ship but flag conditions/recommendations
- `REQUEST_MODIFICATIONS` — bounce back to Orchestrator
- `REJECTED`              — restart from intent

## Output

A user-facing assessment with:

- Plain-English summary (what's included, timeline, budget)
- Conditions for success (user inputs needed)
- Risks + mitigations
- Approval CTA (`YES` / `MODIFY` / `REJECT`)
"""


SUB_AGENT_TEAM_BODY = """
# Sub-Agent Team — Execution Layer

Specialist agents assigned to a session.  Each has:

- **Specialty brief** (one-line description)
- **Tools** (schemas of what they can call)
- **Resources** (files / data they can read or write)
- **System prompt** specific to their craft

## Execution contract

Each Sub-Agent receives a **Task Briefing** with:

- Task ID, title, description, deadline
- Dependencies (which tasks must finish first)
- Success criteria (measurable)
- Deliverables (explicit list of artifacts)
- Available tools & resources
- Context bundle (relevant prior artifacts, NOT full transcripts)

## Communication rules

- Sub-Agents **never** message the User.
- All cross-Sub-Agent communication routes through the Orchestrator.
- Blockers → escalate to Orchestrator immediately.
- Progress reports → daily check-in to Orchestrator.

## Example roster (dropshipping site)

- Web Dev Visionary (brand + high-level design)
- UX Designer (wireframes, flows)
- UI Designer (mockups, design system)
- Shopify Developer (store setup, products, theme)
- Backend Engineer (payments, security, integrations)
- Copywriter (product copy, SEO descriptions)
- Content Creator (blog posts)
- QA Engineer (testing, accessibility, performance)
- Analytics Engineer (GA, Hotjar, dashboards)
- DevOps Engineer (deploy, monitoring)
"""


TASK_PLAN_BODY = """
# Task Plan — Artifact Schema

The Task Plan is the **central artifact** the Orchestrator emits and the
Judge validates.  Structured JSON, never free-form prose.

```json
{
  "id": "<slug>",
  "user_intent_ref": "<id>",
  "metadata": {
    "created_at": "...",
    "status": "draft | ready_for_review | approved | in_progress | complete",
    "total_budget": "...",
    "total_timeline": "..."
  },
  "phases": [
    {
      "id": "phase-N",
      "name": "...",
      "owner": "<agent_name>",
      "tasks": [
        {
          "id": "task-N.M",
          "title": "...",
          "description": "...",
          "assigned_to": "<agent_name>",
          "deadline": "YYYY-MM-DD",
          "dependencies": ["task-X.Y"],
          "estimated_cost": "...",
          "success_criteria": ["..."],
          "resources_needed": ["..."],
          "status": "pending | in_progress | done | blocked",
          "deliverables": ["..."]
        }
      ]
    }
  ],
  "sub_agent_roster": [
    {"agent_id": "...", "assigned_tasks": [...], "total_allocated_cost": "...", "status": "..."}
  ],
  "timeline_gantt": {"phase-N": "Week X (date to date)"},
  "risk_assessment": [
    {"risk": "...", "impact": "low|med|high", "likelihood": "low|med|high",
     "mitigation": "...", "contingency": "..."}
  ]
}
```

The Orchestrator mutates this via `Update_Plan`.  The Judge consumes it
via `Get_Plan`.  Sub-Agents receive **slices** of it as Task Briefings.
"""


INTENT_SUMMARY_BODY = """
# User Intent Summary — Artifact

Output of Phase 1 (Intent Clarifier).  Input to Phase 2 (Orchestrator).

Structured JSON capturing what the user actually wants, distilled from
the questionnaire.  See Intent Clarifier's output schema for shape.
"""


ASSESSMENT_REPORT_BODY = """
# Assessment Report — Artifact

Output of Phase 3 (Judge).  Drives user approval gate before execution.

```json
{
  "plan_id": "...",
  "overall_verdict": "APPROVED | APPROVED_WITH_NOTES | REQUEST_MODIFICATIONS | REJECTED",
  "confidence_score": 0.85,
  "completeness": {...},
  "feasibility": {...},
  "risks": [...],
  "recommendations": {...},
  "user_facing_summary": "<markdown for chat UI>"
}
```
"""


# ----------------------------------------------------------------------
# Phase-step content (short — each step's full detail lives in detail_md)
# ----------------------------------------------------------------------

PHASE1_STEPS = [
    ("Receive raw user prompt",
     "intent_clarifier",
     "*'Build me a website for a dropshipping item'* — vague, lazy, lacks scope.  Normal."),
    ("Generate domain-specific questionnaire (5-10 Qs)",
     "intent_clarifier",
     "Pick questions that **unlock the most info early**: budget → scope; audience → tone; timeline → priority cuts."),
    ("Ask progressively, one Q at a time",
     "intent_clarifier",
     "Conversational, not robotic.  Acknowledge each answer before the next Q."),
    ("Synthesize User Intent Summary (structured JSON)",
     "intent_clarifier",
     "Core request, audience, scope, budget, timeline, must-haves vs nice-to-haves, success criteria, constraints, tech hints."),
    ("Hand off to Orchestrator",
     "intent_clarifier",
     "Emit Intent Summary artifact, transition to Phase 2."),
]

PHASE2_STEPS = [
    ("Parse Intent Summary",
     "orchestrator",
     "Identify domain, key stakeholders, hard constraints."),
    ("Get_Sub_Agent_Summary()",
     "orchestrator",
     "Retrieve roster + capabilities of all available Sub-Agents for this session."),
    ("Ask_User_Questions() for remaining gaps",
     "orchestrator",
     "Anything Intent Clarifier missed.  Keep it tight: 2-5 questions max."),
    ("Consult_Sub_Agent() — feasibility checks",
     "orchestrator",
     "*'Can we build this in 6 weeks?'* → Shopify Dev: *'Yes if images by week 2.'*\n\nFeed answers back into plan."),
    ("Update_Plan() — iteratively build the DAG",
     "orchestrator",
     "Add phases, tasks, dependencies, owners, deadlines, success criteria, deliverables."),
    ("Finalize_Plan() — hand off to Judge",
     "orchestrator",
     "Lock the draft, transition to Phase 3."),
]

PHASE3_STEPS = [
    ("Validate completeness",
     "judge",
     "Every must-have covered?  Any orphan tasks?  Any nice-to-haves missed within budget?"),
    ("Validate feasibility",
     "judge",
     "Timeline math: critical path vs deadline.  Budget math: allocated vs ceiling.  Resource math: agent availability."),
    ("Risk analysis + mitigation",
     "judge",
     "Top 3-5 risks with impact × likelihood.  Each with mitigation + contingency."),
    ("Verdict + user-facing summary",
     "judge",
     "APPROVED / APPROVED_WITH_NOTES / REQUEST_MODIFICATIONS / REJECTED + plain-English presentation."),
    ("User approval gate",
     "user",
     "User clicks YES / MODIFY / REJECT.  YES → Phase 4.  MODIFY → back to Orchestrator.  REJECT → restart."),
]

PHASE4_STEPS = [
    ("Brief each Sub-Agent with their Task Briefing",
     "orchestrator",
     "Slice the Task Plan: each agent gets their tasks + context bundle (NOT full transcripts)."),
    ("Sub-Agents execute in parallel where DAG allows",
     "sub_agents",
     "Topological order, parallel dispatch of all ready nodes."),
    ("Progress check-ins + blocker escalation",
     "sub_agents",
     "Daily report to Orchestrator.  Blockers escalate immediately."),
    ("Orchestrator validates deliverables per task",
     "orchestrator",
     "Acceptance criteria check.  Approve → unblock dependents.  Reject → request revision."),
    ("Final delivery to User",
     "orchestrator",
     "Bundle artifacts, links, status.  Close session."),
]


# ----------------------------------------------------------------------
# Structured agent metadata
# ----------------------------------------------------------------------
# Each agent gets a meta dict with modular fields:
#   model          -- the LLM intended to back this agent
#   system_prompt  -- the system prompt verbatim (raw text)
#   tools          -- list of {name, purpose} dicts; CRUD-able from the UI
#   output_schema  -- raw JSON template the agent emits (string, pretty-printed)
#   notes_md       -- catch-all markdown for context the structured fields miss
#
# Stored as JSON in nodes.meta_json.  The panel renderer prefers these
# fields over body_md for agent-kind nodes; artifacts keep using body_md.
import json

INTENT_CLARIFIER_META = {
    "model": "claude-sonnet-4.5",
    "system_prompt": (
        "You are the Intent Clarifier. Your job is to transform vague user requests "
        "into structured information that the Orchestrator can use.\n\n"
        "Input: Raw user request (likely incomplete, vague, or lacking detail)\n"
        "Output: 5-10 contextual questions + collected answers, synthesized into a "
        "User Intent Summary.\n\n"
        "Rules:\n"
        "- Ask questions progressively, not all at once. Wait for answers.\n"
        "- Questions are domain-specific (website -> ask about design, hosting, audience; "
        "video -> ask about length, platform, style).\n"
        "- Prioritize questions that unlock the most information early.\n"
        "- Be conversational, not robotic. Acknowledge each answer.\n"
        "- After all answers, synthesize a User Intent Summary."
    ),
    "tools": [
        {"name": "Ask_Question", "purpose": "Pose one contextual question to the user"},
        {"name": "Record_Answer", "purpose": "Append answer to the running questionnaire"},
        {"name": "Synthesize_Intent", "purpose": "Build the final User Intent Summary JSON"},
    ],
    "output_schema": json.dumps({
        "raw_request": "...",
        "questionnaire": [{"q": "...", "a": "..."}],
        "synthesized_intent": {
            "core_request": "...",
            "target_audience": "...",
            "scope": "...",
            "budget": "...",
            "timeline": "...",
            "must_haves": ["..."],
            "nice_to_haves": ["..."],
            "success_criteria": "...",
            "constraints": ["..."],
        },
        "confidence": 0.0,
    }, indent=2),
    "notes_md": "Stops asking once **confidence > 0.8** or after **10 questions**, whichever comes first.",
}

ORCHESTRATOR_META = {
    "model": "claude-opus-4",
    "system_prompt": (
        "You are the Orchestrator. You are a PURE ROUTER -- you NEVER execute work yourself.\n\n"
        "Your job: take a User Intent Summary and produce a complete, vetted Task Plan by "
        "orchestrating sub-agents and the user. You operate in a planning loop:\n\n"
        "  1. Read the latest User Intent Summary (or last Task Plan draft).\n"
        "  2. Identify gaps, ambiguities, or sub-domains you can't plan without expert input.\n"
        "  3. Call Consult_Sub_Agent() to query specialists for context (NOT to delegate work).\n"
        "  4. If gaps remain, call Ask_User_Questions() with concrete A/B/C/D options.\n"
        "  5. Call Update_Plan() with the latest draft.\n"
        "  6. Repeat from step 2 until confidence is high enough.\n"
        "  7. Call Finalize_Plan() to emit the Task Plan to the Judge.\n\n"
        "Hard rules:\n"
        "- NEVER write code, design assets, or anything substantive yourself.\n"
        "- NEVER delegate execution to sub-agents -- that's the post-approval phase.\n"
        "- ALWAYS prefer concrete A/B/C/D options when asking the user; never open-ended.\n"
        "- Treat sub-agent consults as ADVISORY only; their answers shape the plan."
    ),
    "tools": [
        {"name": "Ask_User_Questions",      "purpose": "Present concrete A/B/C/D choices to the user"},
        {"name": "Update_Plan",             "purpose": "Persist the current Task Plan draft"},
        {"name": "Get_Plan",                "purpose": "Read the current Task Plan draft"},
        {"name": "Consult_Sub_Agent",       "purpose": "Ask a sub-agent for advisory context"},
        {"name": "Get_Sub_Agent_Summary",   "purpose": "Look up what a sub-agent does + its tools"},
        {"name": "Finalize_Plan",           "purpose": "Emit the plan for Judge review"},
    ],
    "output_schema": json.dumps({
        "plan_id": "...",
        "intent_ref": "...",
        "tasks": [
            {
                "id": "T-001",
                "owner_agent": "<sub_agent_key>",
                "description": "...",
                "depends_on": ["T-000"],
                "deliverable": "...",
                "deadline": "...",
                "acceptance_criteria": ["..."],
            }
        ],
        "open_questions": ["..."],
        "consult_log": [{"sub_agent": "...", "question": "...", "answer": "..."}],
        "confidence": 0.0,
    }, indent=2),
    "notes_md": (
        "### The planning loop is iterative\n\n"
        "The Orchestrator rarely nails a plan on the first try.  Each iteration:\n\n"
        "1. Drafts the plan with current info\n"
        "2. Notices a gap (e.g. *\"user said 'Bottomless Bytes' but I see an existing project with that name\"*)\n"
        "3. Consults Sub-Agent(s) for relevant context (*Web Dev Visionary*: \"is this site live? what stack?\")\n"
        "4. Asks the user a precise A/B/C/D question about how to proceed\n"
        "5. Updates the draft and re-evaluates\n\n"
        "Loop exits only when `confidence >= 0.9` AND `open_questions == []`."
    ),
}

JUDGE_META = {
    "model": "claude-opus-4",
    "system_prompt": (
        "You are the Judge / Assessor. You read a Task Plan and decide whether it is "
        "ready for execution. You produce an Assessment Report scoring four dimensions:\n\n"
        "  - Completeness: every task has owner, deliverable, acceptance criteria\n"
        "  - Feasibility:  dependencies form a valid DAG, deadlines realistic, owners qualified\n"
        "  - Risk:         no obvious failure modes, blockers, or single-points-of-failure\n"
        "  - Clarity:      a non-technical user could understand what each task delivers\n\n"
        "Verdict is one of: APPROVE, APPROVE_WITH_NOTES, REQUEST_CHANGES, REJECT."
    ),
    "tools": [
        {"name": "Read_Plan",     "purpose": "Load the Task Plan emitted by Orchestrator"},
        {"name": "Score_Section", "purpose": "Assign a 0-1 score to a single dimension"},
        {"name": "Emit_Verdict",  "purpose": "Produce the final Assessment Report"},
    ],
    "output_schema": json.dumps({
        "plan_id": "...",
        "verdict": "APPROVE | APPROVE_WITH_NOTES | REQUEST_CHANGES | REJECT",
        "scores": {"completeness": 0.0, "feasibility": 0.0, "risk": 0.0, "clarity": 0.0},
        "findings": [
            {"severity": "low|med|high", "area": "...", "detail": "...", "suggestion": "..."}
        ],
        "user_facing_summary": "...",
    }, indent=2),
    "notes_md": "REQUEST_CHANGES routes back to Orchestrator with findings.  APPROVE / APPROVE_WITH_NOTES routes to User.",
}

USER_META = {
    "model": "(human)",
    "system_prompt": "N/A -- the User is the human in the loop, not an LLM.",
    "tools": [
        {"name": "Submit_Request",     "purpose": "Initial vague request to kick off the workflow"},
        {"name": "Answer_Question",    "purpose": "Reply to questionnaire / clarification / approval prompts"},
        {"name": "Approve_Plan",       "purpose": "Greenlight the Task Plan for execution"},
        {"name": "Receive_Delivery",   "purpose": "Accept the final deliverables from Orchestrator"},
    ],
    "output_schema": "",
    "notes_md": "The User is the only non-AI actor on the board.  All loops eventually return here.",
}

SUB_AGENT_TEAM_META = {
    "model": "varies per specialist (typically claude-sonnet-4.5)",
    "system_prompt": (
        "Each specialist agent has its own system prompt tailored to its domain.  "
        "All specialists share the contract:\n\n"
        "- Communicate ONLY with the Orchestrator (never the user, never each other).\n"
        "- During planning: respond with advisory context, not committed work.\n"
        "- During execution: produce the deliverable assigned in your Task entry.\n"
        "- Always include `confidence`, `assumptions`, and `open_questions` in responses."
    ),
    "tools": [
        {"name": "Web_Dev_Visionary",  "purpose": "Architect overall web project strategy"},
        {"name": "UX_Designer",        "purpose": "Wireframes, design system, accessibility"},
        {"name": "Backend_Engineer",   "purpose": "APIs, data model, infra"},
        {"name": "Shopify_Developer",  "purpose": "Storefront, themes, app integrations"},
        {"name": "Copywriter",         "purpose": "Marketing copy, product descriptions"},
        {"name": "SEO_Specialist",     "purpose": "Metadata, schema markup, sitemap"},
        {"name": "QA_Engineer",        "purpose": "Test plans, regression coverage"},
        {"name": "DevOps_Engineer",    "purpose": "CI/CD, hosting, monitoring"},
        {"name": "Legal_Reviewer",     "purpose": "TOS, privacy, GDPR"},
        {"name": "Analytics_Specialist","purpose": "GA4, event tracking, funnels"},
        {"name": "Brand_Strategist",   "purpose": "Voice, palette, identity"},
        {"name": "Product_Photographer","purpose": "Product imagery + post-processing"},
    ],
    "output_schema": json.dumps({
        "sub_agent": "...",
        "context_answer": "...",
        "confidence": 0.0,
        "assumptions": ["..."],
        "open_questions": ["..."],
    }, indent=2),
    "notes_md": "Add or swap specialists by editing this tool list -- the Orchestrator picks them up dynamically.",
}


# ----------------------------------------------------------------------
# Wiring
# ----------------------------------------------------------------------

def _drop_board_if_exists(slug: str) -> None:
    """Idempotent re-seed: nuke prior board with same slug."""
    existing = db.get_board(slug)
    if existing:
        with db.cursor() as cur:
            cur.execute("DELETE FROM boards WHERE id = ?", (existing["id"],))


def seed() -> int:
    db.init_schema()
    _drop_board_if_exists("aio-orchestrator")

    board_id = db.create_board(
        slug="aio-orchestrator",
        name="AIO Orchestrator",
        description="General-purpose AI Task Manager: Intent Clarifier → Orchestrator → Judge → Sub-Agents.",
    )

    # ---- Architecture view: chronological left-to-right layout ----
    # Top row  (y=AGENT_Y) = main flow:   User -> IntentClarifier -> Orchestrator -> Judge -> Sub-Agents
    # Bottom row (y=ART_Y) = artifacts, sitting between their producer and consumer
    # Spacing chosen so 230px cards have ~70px gap between them.
    COL = 300            # horizontal spacing between agent slots
    X0  = 60             # left margin
    AGENT_Y = 60
    ART_Y   = 280        # artifacts row
    ART_DX  = COL // 2   # artifacts sit halfway between producer and consumer

    def agent_x(i: int) -> int: return X0 + COL * i
    def art_x(i: int)   -> int: return X0 + COL * i + ART_DX

    n: dict[str, int] = {}  # key -> id

    # --- Top row: agents in chronological order ---
    n["user"] = db.insert_node(
        board_id, key="user", kind="agent",
        name="User",
        brief="The human kicking off the workflow",
        body_md=USER_BODY, meta_json=json.dumps(USER_META), color="#94a3b8",
        arch_x=agent_x(0), arch_y=AGENT_Y,
    )
    n["intent_clarifier"] = db.insert_node(
        board_id, key="intent_clarifier", kind="agent",
        name="Intent Clarifier",
        brief="Turns vague requests into structured intent via questionnaire",
        body_md=INTENT_CLARIFIER_BODY, meta_json=json.dumps(INTENT_CLARIFIER_META),
        color="#22d3ee",
        arch_x=agent_x(1), arch_y=AGENT_Y,
    )
    n["orchestrator"] = db.insert_node(
        board_id, key="orchestrator", kind="agent",
        name="Orchestrator",
        brief="Pure routing & planning -- never executes",
        body_md=ORCHESTRATOR_BODY, meta_json=json.dumps(ORCHESTRATOR_META),
        color="#a78bfa",
        arch_x=agent_x(2), arch_y=AGENT_Y,
    )
    n["judge"] = db.insert_node(
        board_id, key="judge", kind="agent",
        name="Judge / Assessor",
        brief="Validates Task Plan before execution",
        body_md=JUDGE_BODY, meta_json=json.dumps(JUDGE_META), color="#fbbf24",
        arch_x=agent_x(3), arch_y=AGENT_Y,
    )
    n["sub_agents"] = db.insert_node(
        board_id, key="sub_agents", kind="agent",
        name="Sub-Agent Team",
        brief="Specialists who do the actual work",
        body_md=SUB_AGENT_TEAM_BODY, meta_json=json.dumps(SUB_AGENT_TEAM_META),
        color="#34d399",
        arch_x=agent_x(4), arch_y=AGENT_Y,
    )

    # --- Bottom row: artifacts between their producer and consumer ---
    n["intent_summary"] = db.insert_node(
        board_id, key="intent_summary", kind="artifact",
        name="User Intent Summary",
        brief="Structured output of Phase 1",
        body_md=INTENT_SUMMARY_BODY, color="#67e8f9",
        arch_x=art_x(1), arch_y=ART_Y,   # between IntentClarifier (1) and Orchestrator (2)
    )
    n["task_plan"] = db.insert_node(
        board_id, key="task_plan", kind="artifact",
        name="Task Plan",
        brief="DAG of tasks, owners, deadlines, deliverables",
        body_md=TASK_PLAN_BODY, color="#c4b5fd",
        arch_x=art_x(2), arch_y=ART_Y,   # between Orchestrator (2) and Judge (3)
    )
    n["assessment"] = db.insert_node(
        board_id, key="assessment", kind="artifact",
        name="Assessment Report",
        brief="Judge's verdict + user-facing summary",
        body_md=ASSESSMENT_REPORT_BODY, color="#fcd34d",
        arch_x=art_x(3), arch_y=ART_Y,   # between Judge (3) and Sub-Agents (4)
    )

    # ---- Edges: chronological, with explicit planning-loop steps ----
    # The Orchestrator's planning isn't single-shot.  Steps 5-9 form an
    # iterative loop: consult sub-agents, ping user for clarification when a
    # roadblock appears, refine the draft.  The loop exits when confidence is
    # high enough and Update_Plan emits the final draft to the Judge.
    step = 0
    def link(src: str, dst: str, label: str = "", kind: str = "comms",
             numbered: bool = True) -> None:
        nonlocal step
        order = None
        if numbered:
            step += 1
            order = step
        db.insert_edge(board_id, n[src], n[dst], label, kind, order)

    # ---- Phase 1: Intent gathering ----
    link("user", "intent_clarifier", "raw prompt", "comms")
    link("intent_clarifier", "user", "questionnaire", "comms")
    link("intent_clarifier", "intent_summary", "emit", "flow")

    # ---- Phase 2: Planning loop (orchestrator iterates until confident) ----
    link("intent_summary", "orchestrator", "consume", "flow")
    link("orchestrator", "sub_agents", "consult: context?", "comms")
    link("sub_agents", "orchestrator", "advisory context", "comms")
    link("orchestrator", "user", "clarify gap (A/B/C/D)", "comms")
    link("user", "orchestrator", "choice", "comms")
    link("orchestrator", "task_plan", "Update_Plan (loop until confident)", "flow")

    # ---- Phase 3: Judgment ----
    link("task_plan", "judge", "review", "flow")
    link("judge", "assessment", "emit", "flow")
    link("assessment", "user", "approval gate", "comms")

    # ---- Phase 4: Execution ----
    link("orchestrator", "sub_agents", "brief & dispatch", "flow")
    link("sub_agents", "orchestrator", "deliverables", "flow")
    link("orchestrator", "user", "final delivery", "flow")

    # ---- Phases view: 4 phase cards + steps each ----
    phase_specs = [
        ("phase_1", "Phase 1 — Intent Clarification", "#22d3ee",
         "Lazy user input → structured Intent Summary via progressive questionnaire.",
         PHASE1_STEPS),
        ("phase_2", "Phase 2 — Orchestration", "#a78bfa",
         "Build the Task Plan: consult Sub-Agents, fill gaps, lock the DAG.",
         PHASE2_STEPS),
        ("phase_3", "Phase 3 — Judgment", "#fbbf24",
         "Validate the plan, surface risks, hand a clear yes/no to the user.",
         PHASE3_STEPS),
        ("phase_4", "Phase 4 — Execution", "#34d399",
         "Sub-Agents do the work; Orchestrator brokers everything.",
         PHASE4_STEPS),
    ]
    for order, (key, name, color, brief, steps) in enumerate(phase_specs, start=1):
        phase_id = db.insert_node(
            board_id, key=key, kind="phase",
            name=name, brief=brief, body_md=brief, color=color,
            phase_order=order,
        )
        for step_idx, (action, actor_key, detail_md) in enumerate(steps, start=1):
            db.insert_phase_step(
                phase_node_id=phase_id,
                order_idx=step_idx,
                action=action,
                actor_node_id=n.get(actor_key),
                detail_md=detail_md,
            )

    return board_id


if __name__ == "__main__":
    bid = seed()
    print(f"Seeded board id={bid} slug='aio-orchestrator'")
