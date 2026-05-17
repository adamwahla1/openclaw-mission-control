# SUPERSEDED - Historical OpenClaw-First Plan

This plan is preserved as historical context only.

It no longer describes the current product direction.

Current direction as of 2026-05-17:

- Mission Control is native-runtime-first.
- OpenClaw is optional adapter support, not the required execution layer.
- OpenRouter is the first provider.
- Pydantic AI and LangGraph are the intended native runtime foundations.
- The current source of truth is `docs/handover/HANDOVER.md`.

Do not implement new work from this plan unless the user explicitly asks to
return to the OpenClaw-first architecture.

---

# OpenClaw Mission Control - Master Plan v2

## Context

Building the definitive Mission Control for OpenClaw — a best-of-breed combination of every good feature from the top open-source projects, plus 4 unique differentiators. This is not a parallel system; it IS OpenClaw's operational surface. Everything flows through the OpenClaw Gateway. Bidirectional sync — agents, sessions, memories, skills all live in OpenClaw and are managed through this dashboard.

### Reference Projects Studied

| Project | Stars | Stack | Features We're Taking |
|---------|-------|-------|----------------------|
| **builderz-labs/mission-control** | 4.4k | Next.js 16, SQLite, Zustand | 32-panel SPA architecture, Aegis quality gates, Skills Hub (ClawdHub + skills.sh), Memory Knowledge Graph, agent eval framework (4-layer), security audit + trust scoring, recurring tasks (NLP → cron), cost tracking (per-model), webhook system (HMAC-SHA256), activity feed, framework adapters, Claude Code bridge, i18n (10 locales) |
| **abhi1693/openclaw-mission-control** | 3.8k | TS + Python backend | Governance model (orgs → board groups → boards → tasks), approval workflows, gateway-aware orchestration, separate frontend/backend pattern, API-first design |
| **crshdn/mission-control (Autensa)** | 2k | Next.js 14, SQLite | **Autopilot pipeline** (Research → Ideation → Swipe → Build → Test → Review → PR), Convoy Mode (parallel multi-agent DAG), Agent Skill Creation Loop (Bayesian confidence), Operator Chat (queued notes + DMs), per-task sessions, workspace isolation (git worktrees), checkpoint/crash recovery, preference learning, Maybe Pool, automation tiers (Supervised/Semi-Auto/Full Auto), budget caps |
| **WW-AI-Lab/openclaw-office** | 559 | TypeScript, SVG isometric | 2D isometric office, agents as employees, workstations = sessions, meeting rooms = collaboration, WebSocket-driven animations |
| **wickedapp/openclaw-office** | 139 | JavaScript, Next.js | AI-generated scenes, sprite rendering, animated message envelopes between agents, RequestPipeline visualization, notify plugin for gateway events |

### OpenClaw Gateway Protocol (How It All Connects)

- **Transport**: WebSocket, JSON text frames. Single multiplexed port.
- **Handshake**: `connect` RPC → role (`operator`) + scopes (`operator.read`, `operator.write`, `operator.admin`)
- **Agent CRUD**: `agents.list`, `agents.create`, `agents.update`, `agents.delete`, `agents.files.*` for workspace files
- **Sessions**: `sessions.create` (per-task), `sessions.send`, `sessions.subscribe` for live event streams
- **Chat execution**: `chat.send`, `chat.history`, `chat.abort`, `chat.inject`
- **Real-time**: Broadcast events scope-gated by permissions. Agent events, tool results, session updates via SSE/WS.
- **Models**: `models.list` returns runtime-allowed catalog. All AI runs through OpenClaw's model routing.
- **Config**: `config.get/set/patch` for runtime configuration changes
- **Approvals**: `exec.approvals.*` for human-in-the-loop gating

**Critical design principle**: Our backend acts as an `operator` role client to the OpenClaw Gateway. We don't run AI ourselves — we dispatch to OpenClaw, which routes to its configured AI providers. Every agent we create via the dashboard is a real OpenClaw agent. Every session is an OpenClaw session. Memory updates go through OpenClaw's agent workspace files. Bidirectional.

---

## Phased Approach

### Phase 1 — Foundation + Core Task System
Get the architecture running, gateway connected, Kanban board working, multi-agent dispatch functional, live agent view streaming.

### Phase 2 — Smart Projects + Debate Room
Auto-bundling engine, project dashboards, handover docs. Debate room with multi-agent deliberation.

### Phase 3 — Memory Neural Map + Virtual Office
D3.js memory graph, agent memory CRUD synced with OpenClaw. Canvas-based isometric office with sprite animations.

### Phase 4 — Autopilot + Skills Hub + Advanced Features
Product autopilot pipeline, skills marketplace (external + internal), quality gates, agent evals, cost tracking, security audit, recurring tasks, webhooks, approval workflows, workspace isolation.

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Frontend** | React 19 + Vite + TypeScript | SPA shell matching builderz-labs pattern, fast HMR |
| **Backend** | FastAPI (Python) | Our runtime supports Python, separate backend (abhi1693 pattern), easy async WebSocket handling for gateway bridge |
| **Database** | SQLite via `aiosqlite` (WAL mode) | Every reference project uses SQLite. Zero-dependency. Local-first. |
| **State Management** | Zustand 5 | Same as builderz-labs, lightweight, great WebSocket/SSE integration |
| **Styling** | Tailwind CSS 4 + shadcn/ui | Apple design guidelines, dark theme, consistent component library |
| **Real-time** | WebSocket (backend ↔ OpenClaw Gateway) + SSE (frontend ← backend) | Gateway is WS-native. SSE to frontend for live streams. |
| **Charts** | Recharts | Same as builderz-labs, token/cost dashboards |
| **Memory Viz** | D3.js force-directed graph | Neural map visualization, node clustering, relationship edges |
| **Office Viz** | HTML5 Canvas + sprite engine | Better perf than SVG for animations (WW-AI-Lab's SVG approach has limits) |
| **AI/Models** | **OpenClaw Gateway** (all models routed through OC) | No direct provider calls. OC handles model routing, failover, usage tracking. |
| **Validation** | Zod (frontend) + Pydantic (backend) | Type-safe across the stack |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  React SPA (Vite + TypeScript + Zustand)                          │
│  ┌────────┬────────┬────────┬────────┬────────┬────────┬────────┐ │
│  │Dash-   │Task    │Proj-   │Debate  │Memory  │Virtual │Auto-   │ │
│  │board   │Board   │ects    │Room    │Map     │Office  │pilot   │ │
│  │        │(Kanban)│        │        │(D3.js) │(Canvas)│        │ │
│  │Overview│Agent   │Time-   │Group   │Neural  │Sprite  │Swipe   │ │
│  │Stats   │Live    │line    │Chat    │Graph   │Engine  │Cards   │ │
│  │Feed    │View    │Files   │Rounds  │Search  │Anim    │Pipeline│ │
│  ├────────┴────────┴────────┴────────┴────────┴────────┴────────┤ │
│  │ Skills Hub │ Cost Tracking │ Security Audit │ Settings/Admin  │ │
│  └──────────────────────┬───────────────────────────────────────┘ │
│                    SSE + REST                                     │
├──────────────────────────┼────────────────────────────────────────┤
│  FastAPI Backend (Python)│                                        │
│  ┌───────────────────────┴──────────────────────────────────────┐ │
│  │                                                              │ │
│  │  Gateway Bridge (WS operator client ↔ OpenClaw Gateway)      │ │
│  │  ├─ Maintains persistent WS connection                       │ │
│  │  ├─ Subscribes to session events, agent events               │ │
│  │  ├─ Translates gateway events → SSE broadcasts to frontend   │ │
│  │  └─ All agent/session/model ops proxy through here           │ │
│  │                                                              │ │
│  │  Orchestrator Engine                                         │ │
│  │  ├─ Task decomposition (breaks complex tasks into subtasks)  │ │
│  │  ├─ Agent Factory (intelligent agent creation — see below)   │ │
│  │  ├─ Dispatch via gateway sessions.create + sessions.send     │ │
│  │  ├─ Convoy Mode (parallel DAG execution)                     │ │
│  │  └─ Checkpoint/crash recovery                                │ │
│  │                                                              │ │
│  │  Project Bundler (auto-detection + clustering)               │ │
│  │  Debate Engine (multi-round deliberation + convergence)      │ │
│  │  Memory Manager (graph ops, synced to OC agent workspace)    │ │
│  │  Autopilot Engine (research → ideation → build pipeline)     │ │
│  │  Skills Registry (external ClawdHub + internal skill DB)     │ │
│  │  Eval Framework (output/trace/component/drift evals)         │ │
│  │  Security Engine (trust scoring, secret detection, audit)    │ │
│  │  Webhook Manager (outbound, HMAC-SHA256, retry + backoff)    │ │
│  │  Scheduler (NLP → cron recurring tasks)                      │ │
│  │  SSE Broadcaster (live events to all connected frontends)    │ │
│  │                                                              │ │
│  └──────────┬───────────────────────────┬───────────────────────┘ │
│             │                           │                         │
│     ┌───────┴────────┐         ┌────────┴──────────────┐         │
│     │  SQLite (WAL)  │         │  OpenClaw Gateway      │         │
│     │  MC-local data │         │  ws://localhost:18789   │         │
│     │  (tasks, proj, │         │  (agents, sessions,     │         │
│     │   debates, UI  │         │   models, memory,       │         │
│     │   state, costs)│         │   skills, execution)    │         │
│     └────────────────┘         └────────────────────────┘         │
└───────────────────────────────────────────────────────────────────┘
```

**Data split**: SQLite stores Mission Control UI state (task board positions, project groupings, debate transcripts, UI preferences, local cost aggregations). The OpenClaw Gateway is the source of truth for agents, sessions, models, agent workspaces, and execution. We read from both, write to both, keep them in sync.

---

## Intelligent Agent Creation (Agent Factory)

This is a core differentiator. When the orchestrator needs to create a specialist agent, it doesn't just slap together a basic "You are a {role}" prompt.

### The Agent Architect Process:
1. **Role Analysis**: Determine exactly what the agent needs to do (e.g., "SEO optimizer for Amazon listings")
2. **Best-Practice Research**: The orchestrator agent uses OpenClaw's own capabilities to research current best prompting techniques for this role — chain-of-thought structuring, few-shot examples, constraint framing, output formatting
3. **SOUL Construction**: Build the agent's SOUL (System-Oriented Universal Language — OpenClaw's agent personality system) with:
   - Precise role definition with domain expertise markers
   - Behavioral constraints and guardrails
   - Output format specifications
   - Tool usage patterns specific to the role
   - Error handling and self-correction instructions
   - Collaboration protocols (how to communicate with orchestrator and sibling agents)
4. **Skill Injection**: Check the skills registry for relevant proven skills. Inject highest-confidence skills as primary instructions (Autensa's Bayesian pattern).
5. **Agent Registration**: Create via `agents.create` on the gateway with full SOUL config + workspace files via `agents.files.set`
6. **Validation**: Run a quick test prompt to verify the agent responds correctly for its role before dispatching real work

### Manual Agent Creation:
Users can also create agents manually through the UI. The Agent Factory will offer an "Optimize" button that runs the same research + SOUL construction process on a user-drafted agent, suggesting improvements.

---

## Feature Inventory (All Phases)

### Phase 1 — Foundation + Core Task System

**Infrastructure:**
- [ ] React + Vite + TypeScript frontend scaffold with Tailwind + shadcn/ui
- [ ] FastAPI backend with SQLite, migration system, CORS
- [ ] Gateway Bridge — persistent WS operator connection to OpenClaw Gateway
- [ ] SSE broadcaster for real-time frontend events
- [ ] Navigation shell: sidebar with all pages, header bar, live status indicator
- [ ] Auth system — token-based matching OpenClaw gateway token
- [ ] start.sh dual-service launcher

**Task System (from builderz-labs + crshdn + abhi1693):**
- [ ] Kanban board — 7 columns (Inbox → Assigned → In Progress → Review → Quality Review → Done → Archived)
- [ ] Drag-and-drop via @dnd-kit
- [ ] Task CRUD — title, description, requirements, priority (critical/high/medium/low), tags, file attachments
- [ ] Task assignment to agents (manual or auto-dispatch)
- [ ] Per-task sessions — each task gets its own OpenClaw session via `sessions.create`
- [ ] Sub-task creation — tasks can have child tasks for decomposition
- [ ] Task threading — comments and activity notes on tasks
- [ ] Orchestrator engine — receives tasks, decomposes, spawns agents, dispatches
- [ ] Agent Factory — intelligent agent creation (research + SOUL + skill injection)
- [ ] Convoy Mode — parallel multi-agent DAG execution for complex tasks
- [ ] Agent Live View — real-time message stream showing exact agent-to-agent communication with full wording
- [ ] Agent management panel — list, create, edit, retire agents (synced with OC)
- [ ] Operator Chat — queued notes + direct messages to agents mid-task (crshdn pattern)

**Dashboard (from builderz-labs):**
- [ ] Overview panel — active tasks, agent status, gateway connection health
- [ ] Activity feed — real-time stream of all events (filterable by type/agent/time)
- [ ] Quick stats — tasks completed today, agents active, tokens used

### Phase 2 — Smart Projects + Debate Room

**Smart Projects (our unique feature):**
- [ ] Project CRUD + manual task grouping
- [ ] Auto-detection engine — semantic similarity on task descriptions (embeddings via OpenClaw)
- [ ] Clustering — cosine similarity > threshold → suggest grouping. Auto-group at 3+ related tasks.
- [ ] Project dashboard: timeline view, all task statuses, cost aggregation
- [ ] Completed files browser — all output files organized by task within project
- [ ] Handover documents — auto-generated after each task: what was requested, what was done, decisions made, files produced, open questions
- [ ] Key assets section — pinnable files/links that keep surfacing across project tasks
- [ ] Project-scoped search — find anything within a project

**Agent Debate Room (our unique feature):**
- [ ] Dedicated `/debate` page with group-chat UI
- [ ] Specialist agent pool — Architect, Frontend, Backend, DevOps, Security, Product (+ custom)
- [ ] Debate flow: User posts topic → Orchestrator distributes → Round 1 (initial positions) → Round 2+ (rebuttals/agreements) → Convergence or max rounds → Conclusion
- [ ] Each specialist is a real OpenClaw agent with role-specific SOUL
- [ ] Convergence detection — compare positions each round, declare convergence when agents align
- [ ] Orchestrator compiles follow-up questions if agents need user clarification
- [ ] Final conclusion document — synthesized from all positions
- [ ] Debate history — browse past debates, search, reference in tasks
- [ ] Color-coded agent avatars, collapsible rounds, highlighted conclusion

### Phase 3 — Memory Neural Map + Virtual Office

**Memory Neural Map (our unique feature):**
- [ ] Memory node types: Facts, Preferences, Decisions, Skills Learned, Errors, Context
- [ ] Auto-capture from task completions, debate conclusions, agent interactions
- [ ] Memory synced with OpenClaw agent workspace (bidirectional via `agents.files.*`)
- [ ] D3.js force-directed graph visualization:
  - Nodes colored by type, sized by importance/access frequency
  - Edges show relationships (temporal, causal, topical)
  - Cluster by project/topic
  - Hover = content preview, click = full detail
  - Time slider to see memory evolution
  - Memory decay — older/unused memories fade visually
- [ ] Manual memory CRUD — create, edit, pin, delete memories
- [ ] Semantic memory search (via OpenClaw embeddings)
- [ ] Memory injection into agent context — relevant memories auto-injected when dispatching tasks

**Virtual Office (our unique feature):**
- [ ] HTML5 Canvas isometric office renderer
- [ ] Office layout: desks (one per agent), meeting room, break room, server room
- [ ] Agent sprites with state animations:
  - Idle (sitting at desk)
  - Working (typing animation)
  - Walking (moving between areas)
  - Meeting (gathered in meeting room — debates)
  - Thinking (thought bubble)
  - Communicating (animated message envelope between agents)
  - Celebrating (task complete)
- [ ] Real-time state mapping — gateway events drive sprite positions:
  - Agent assigned task → walks to desk, starts typing
  - Agents in debate → walk to meeting room
  - Agent idle → break room
  - Task complete → celebration
- [ ] Agent name labels, status indicators
- [ ] Customizable sprite styles
- [ ] Gateway connection status shown as server room health

### Phase 4 — Autopilot + Skills + Advanced

**Autopilot Pipeline (from crshdn/Autensa):**
- [ ] Product registration — point at a repo + live URL
- [ ] Autonomous research cycle — AI analyzes codebase, competitors, SEO, UX gaps
- [ ] AI-powered ideation — scored feature ideas (impact, feasibility, size)
- [ ] Swipe interface — Pass/Maybe/Yes/Now! (Tinder-style cards)
- [ ] Preference learning — swipe history trains per-product model
- [ ] Maybe Pool — auto-resurface after configurable period
- [ ] Build pipeline — approved ideas flow: Plan → Build → Test → Review → PR
- [ ] Automation tiers — Supervised / Semi-Auto / Full Auto per product
- [ ] Product Program (Karpathy AutoResearch pattern) — living document that evolves
- [ ] Research + ideation scheduling (configurable cron)

**Skills Hub (both external + internal):**
- [ ] External registry browser — ClawdHub + skills.sh browsing/install
- [ ] Security scanner — prompt injection, credential leaks, exfiltration, obfuscation checks before install
- [ ] Internal skill library — agents auto-create skills from completed tasks
- [ ] Bayesian confidence scoring — skills promoted based on proven success
- [ ] Skill injection at dispatch — highest-confidence matching skills injected as instructions
- [ ] Bidirectional disk ↔ DB sync (builderz-labs pattern)
- [ ] Skill sharing between agents — orchestrator can transfer proven skills across agents
- [ ] 5 skill roots: `~/.agents/skills`, `~/.openclaw/skills`, project-local, custom paths

**Quality Gates (from builderz-labs — Aegis):**
- [ ] Review system that blocks task completion without sign-off
- [ ] Configurable gate rules per task type
- [ ] Auto-review by reviewer agents + manual operator approval

**Agent Eval Framework (from builderz-labs):**
- [ ] Output evals — task completion scoring against golden datasets
- [ ] Trace evals — convergence/loop detection
- [ ] Component evals — tool reliability with p50/p95/p99 latency
- [ ] Drift detection — 10% threshold vs 4-week rolling baseline

**Cost Tracking (from builderz-labs + crshdn):**
- [ ] Per-task, per-agent, per-model, per-project cost breakdowns
- [ ] Token usage dashboard with trend charts (Recharts)
- [ ] Daily and monthly budget caps — auto-pause dispatch when exceeded
- [ ] Session-level granularity via `sessions.usage` + `usage.cost` gateway RPCs

**Security Audit (from builderz-labs):**
- [ ] Real-time posture scoring (0-100)
- [ ] Secret detection across agent messages
- [ ] MCP tool call auditing
- [ ] Injection attempt tracking
- [ ] Per-agent trust scores
- [ ] Hook profiles (minimal/standard/strict)

**Recurring Tasks (from builderz-labs):**
- [ ] Natural language scheduling ("every morning at 9am")
- [ ] NLP → cron parser
- [ ] Template-clone pattern: original stays as template, spawns dated child tasks

**Webhooks (from builderz-labs):**
- [ ] Outbound webhooks with delivery history
- [ ] Retry with exponential backoff + circuit breaker
- [ ] HMAC-SHA256 signature verification
- [ ] GitHub Issues sync with label/assignee mapping

**Workspace Isolation (from crshdn):**
- [ ] Git worktrees for repo-backed tasks
- [ ] Task sandboxes for local/no-repo tasks
- [ ] Port allocation range for dev servers
- [ ] Serialized merge queue with conflict detection

**Checkpoint & Crash Recovery (from crshdn):**
- [ ] Agent progress saved at configurable checkpoints
- [ ] Crash → resume from last checkpoint, not from scratch
- [ ] Checkpoint history visible per task

**Approval Workflows (from abhi1693):**
- [ ] Route sensitive actions through explicit approval flows
- [ ] Decision trails attached to work items
- [ ] Approval UI with approve/reject + notes

**Additional:**
- [ ] i18n support (at least English, with structure for more)
- [ ] Keyboard shortcuts throughout
- [ ] Dark/light theme toggle
- [ ] System diagnostics panel (gateway health, DB status, connection metrics)

---

## Database Schema (SQLite — MC-local state)

```sql
-- Core task system
tasks (id TEXT PK, title, description, status, priority, board_id, project_id,
       assigned_agent_id, parent_task_id, gateway_session_id, 
       template_id, cron_expression, is_template BOOL,
       created_at, updated_at)

task_comments (id, task_id FK, author_type, author_id, content, created_at)

task_attachments (id, task_id FK, filename, filepath, mime_type, size, created_at)

task_checkpoints (id, task_id FK, agent_id, checkpoint_data JSON, created_at)

-- Agent management (MC-side metadata, agents live in OpenClaw)
agents (id TEXT PK, gateway_agent_id, name, role, soul_config JSON, 
        status, trust_score REAL, parent_orchestrator_id,
        created_at, updated_at)

agent_skills (id, agent_id FK, name, description, prompt_template, 
              confidence_score REAL, use_count INT, success_count INT, 
              source TEXT, created_at)

agent_evals (id, agent_id FK, eval_type, score REAL, details JSON, created_at)

-- Task message log (mirrors gateway session messages for UI display)
task_messages (id, task_id FK, agent_id, content, message_type, 
              tool_calls JSON, parent_message_id, round_number, created_at)

-- Projects
projects (id, name, description, status, auto_detected BOOL, 
          detection_method, created_at, updated_at)

project_tasks (project_id FK, task_id FK)

project_files (id, project_id FK, task_id FK, filename, filepath, 
               file_type, pinned BOOL, created_at)

project_handovers (id, project_id FK, task_id FK, content_md, 
                   summary, key_decisions JSON, open_questions JSON, created_at)

-- Debates
debates (id, topic, status, current_round INT, max_rounds INT, 
         conclusion_md, needs_user_input BOOL, created_at, updated_at)

debate_participants (id, debate_id FK, agent_id FK, role, specialty)

debate_messages (id, debate_id FK, agent_id FK, round_number INT, 
                 content, response_to_id FK, stance TEXT, created_at)

debate_questions (id, debate_id FK, question, asked_by_agent_id, 
                  user_response, answered_at, created_at)

-- Memory
memories (id, agent_id, content, memory_type, importance REAL, 
          access_count INT, embedding BLOB, tags JSON, 
          source_type, source_id, last_accessed, decayed BOOL, created_at)

memory_links (id, source_id FK, target_id FK, link_type, 
              strength REAL, created_at)

-- Autopilot
products (id, name, repo_url, live_url, product_program_md,
          status TEXT, automation_tier TEXT, created_at, updated_at)

product_research (id, product_id FK, research_type, findings JSON, created_at)

product_ideas (id, product_id FK, research_id FK, title, description, 
               impact_score REAL, feasibility_score REAL, size_estimate,
               status TEXT, swipe_decision, created_at)

product_preferences (id, product_id FK, category_weights JSON, 
                     complexity_pref REAL, tag_patterns JSON, updated_at)

-- Skills registry
skills (id, name, description, source TEXT, registry_slug, 
        content TEXT, security_scan_result JSON, installed BOOL,
        created_at, updated_at)

-- Cost tracking
cost_entries (id, task_id, agent_id, model, input_tokens INT, 
              output_tokens INT, cost_usd REAL, session_id, created_at)

budget_caps (id, scope TEXT, scope_id, period TEXT, 
             cap_usd REAL, current_usd REAL, paused BOOL)

-- Webhooks
webhooks (id, url, events JSON, secret_hash, active BOOL, 
          created_at, updated_at)

webhook_deliveries (id, webhook_id FK, event, payload JSON, 
                    status_code INT, attempt INT, delivered_at)

-- Security
security_events (id, event_type, agent_id, severity, details JSON, created_at)

-- Activity log
activities (id, event_type, actor_type, actor_id, target_type, 
            target_id, details JSON, created_at)

-- Approvals
approvals (id, action_type, target_type, target_id, requested_by,
           status TEXT, reviewer_notes, decided_at, created_at)

-- Boards (abhi1693 hierarchy)
boards (id, name, board_group_id, description, created_at)
board_groups (id, name, org_id, created_at)

-- Recurring task templates
task_schedules (id, task_template_id FK, cron_expression, 
                nl_expression, active BOOL, last_spawned_at, next_run_at)
```

---

## Implementation Plan (Detailed)

### Phase 1 — Foundation + Core Task System

**1A: Project Scaffold**
1. Init React + Vite + TypeScript frontend (`frontend/`)
2. Init FastAPI + aiosqlite backend (`backend/`)
3. Tailwind CSS 4 + shadcn/ui setup
4. SQLite database module with migration runner
5. start.sh with devguard (Vite port + FastAPI port)
6. CORS configuration, health endpoints

**1B: Gateway Bridge**
7. WebSocket operator client connecting to OpenClaw Gateway
8. Handshake with `connect` RPC (operator role, read+write scopes)
9. Event subscription system — subscribe to session/agent events
10. Gateway event → internal event bus → SSE broadcaster to frontend
11. Proxy layer: frontend REST calls → backend → gateway RPC calls

**1C: Navigation + Layout**
12. App shell — sidebar nav, header bar, content area
13. Pages: Dashboard, Tasks, Projects, Debate, Memory, Office, Skills, Settings
14. Gateway connection status indicator (live/disconnected/reconnecting)
15. Dark theme (Apple design), responsive layout

**1D: Task System**
16. DB schema creation (tasks, agents, task_messages, task_comments)
17. Task CRUD REST endpoints
18. Kanban board UI — 7 columns, drag-and-drop (@dnd-kit)
19. Task creation modal — rich form with priority, tags, attachments
20. Agent management panel — list agents from gateway (`agents.list`), create/edit UI
21. Task assignment — manual assign to agent, triggers `sessions.create`

**1E: Orchestrator + Agent Factory**
22. Orchestrator service — receives task, analyzes complexity
23. Task decomposition — break into subtasks with dependency graph
24. Agent Factory — intelligent agent creation (role analysis → research → SOUL build → skill inject → register via `agents.create`)
25. Dispatch engine — assign subtasks to agents, create sessions, send via `sessions.send`
26. Convoy Mode — parallel execution with dependency-aware scheduling

**1F: Live Agent View + Operator Chat**
27. Agent Live View panel — real-time message stream showing all agent↔agent communication
28. Message display: agent identity, full message content, tool calls, routing decisions
29. Operator Chat — send queued notes or direct messages to agents mid-task
30. Activity feed — real-time event stream on dashboard

### Phase 2 — Smart Projects + Debate Room

**2A: Smart Projects**
31. Project CRUD endpoints + UI
32. Manual task→project grouping
33. Auto-detection engine — embedding similarity via OpenClaw
34. Clustering logic — threshold-based grouping suggestions, auto at 3+ tasks
35. Project dashboard — timeline, status overview, cost aggregation
36. Files browser — organized by task within project
37. Handover doc generator — auto-summary after task completion
38. Key assets section — pin/unpin files and links

**2B: Debate Room**
39. Debate engine — create debate, spawn specialist agents via Agent Factory
40. Round manager — distribute topic, collect responses, manage rebuttals
41. Convergence detector — compare positions, detect agreement
42. Question compiler — if agents need clarification, Orchestrator gathers and asks user
43. Conclusion synthesizer — final document from all positions
44. Debate Room UI — group chat with color-coded agents, collapsible rounds
45. Debate history — browse, search, reference in tasks

### Phase 3 — Memory + Virtual Office

**3A: Memory System**
46. Memory CRUD with types (facts, preferences, decisions, skills, errors)
47. Auto-capture hooks — task completion, debate conclusion → memory creation
48. Memory relationship tracking (temporal, causal, topical links)
49. Bidirectional sync with OpenClaw agent workspace via `agents.files.*`
50. D3.js force-directed graph renderer
51. Node coloring/sizing, edge rendering, cluster layout
52. Time slider, memory decay visualization
53. Semantic search via OpenClaw embeddings
54. Memory injection — relevant memories auto-injected into agent dispatch context

**3B: Virtual Office**
55. Canvas isometric renderer — grid system, camera controls
56. Office layout — desks, meeting room, break room, server room
57. Sprite system — agent character rendering with animation states
58. State machine — idle/working/walking/meeting/thinking/celebrating
59. Gateway event → sprite state mapping
60. Animated message envelopes between agents
61. Agent labels, status badges
62. Server room health = gateway connection status

### Phase 4 — Autopilot + Skills + Advanced

**4A: Autopilot**
63. Product registration + Product Program editor
64. Research cycle — dispatch research agents via OpenClaw
65. Ideation engine — generate scored feature ideas
66. Swipe UI — Tinder-style cards (Pass/Maybe/Yes/Now!)
67. Preference learning model
68. Maybe Pool with auto-resurface
69. Build pipeline — Plan → Build → Test → Review → PR
70. Automation tiers + scheduling

**4B: Skills Hub**
71. External registry client — browse ClawdHub + skills.sh
72. Security scanner — pre-install checks
73. Internal skill library — auto-capture from completed tasks
74. Bayesian confidence scoring + promotion
75. Skill injection at dispatch
76. Bidirectional sync with agent workspace skills dirs

**4C: Quality, Evals, Security**
77. Aegis-style quality gates — configurable review rules
78. Agent eval framework (4-layer)
79. Security audit panel — trust scoring, secret detection, audit log
80. Cost tracking dashboard with budget caps
81. Approval workflow system

**4D: Infrastructure Features**
82. Recurring tasks — NLP→cron parser, template-clone spawning
83. Webhook system — outbound, HMAC, retry, circuit breaker
84. Workspace isolation — git worktrees, task sandboxes
85. Checkpoint/crash recovery
86. Diagnostics panel

---

## Verification Strategy

**Per-phase verification:**

| Check | Method |
|-------|--------|
| Gateway connection | Backend connects to OC, `health` RPC returns ok, agents.list returns data |
| Task CRUD | Create task via UI → verify in DB + visible on Kanban → move between columns |
| Agent dispatch | Submit task → verify orchestrator creates agents on OC → sessions created → messages flowing |
| Live View | Watch agent messages appear in real-time as they work |
| Project auto-bundle | Create 3+ related tasks → verify system suggests/creates project grouping |
| Debate | Start debate → verify multi-round exchange → convergence → conclusion generated |
| Memory | Complete a task → verify memory nodes created → visible on neural map → synced to OC |
| Office | Start task → verify sprite walks to desk and animates working |
| Autopilot | Register product → run research → verify ideas generated → swipe → verify build dispatched |
| Skills | Install from registry → verify security scan → verify injected into next dispatch |
| Bidirectional sync | Create agent in MC → verify appears in OC. Create in OC → verify appears in MC. |

---

## File Structure
```
openclaw_mission_control/
├── backend/
│   ├── main.py                         # FastAPI app + startup
│   ├── config.py                       # Settings (gateway URL, tokens, etc.)
│   ├── database.py                     # SQLite + migrations
│   ├── models/                         # Pydantic schemas
│   │   ├── task.py
│   │   ├── agent.py
│   │   ├── project.py
│   │   ├── debate.py
│   │   ├── memory.py
│   │   ├── product.py
│   │   ├── skill.py
│   │   ├── webhook.py
│   │   └── security.py
│   ├── routers/                        # API endpoints
│   │   ├── tasks.py
│   │   ├── agents.py
│   │   ├── projects.py
│   │   ├── debates.py
│   │   ├── memories.py
│   │   ├── products.py
│   │   ├── skills.py
│   │   ├── webhooks.py
│   │   ├── security.py
│   │   ├── settings.py
│   │   └── events.py                  # SSE endpoint
│   └── services/                       # Business logic
│       ├── gateway_bridge.py           # WS ↔ OpenClaw Gateway
│       ├── orchestrator.py             # Task decomposition + dispatch
│       ├── agent_factory.py            # Intelligent agent creation
│       ├── convoy.py                   # Parallel DAG execution
│       ├── task_manager.py             # Task lifecycle + checkpoints
│       ├── project_bundler.py          # Auto-detection + clustering
│       ├── handover_generator.py       # Auto handover docs
│       ├── debate_engine.py            # Multi-agent deliberation
│       ├── memory_manager.py           # Memory graph + OC sync
│       ├── autopilot.py                # Product improvement pipeline
│       ├── skill_registry.py           # External + internal skills
│       ├── skill_scanner.py            # Security scanning
│       ├── eval_framework.py           # 4-layer agent evals
│       ├── security_engine.py          # Trust scoring + audit
│       ├── cost_tracker.py             # Token/cost aggregation
│       ├── webhook_manager.py          # Outbound webhooks
│       ├── scheduler.py                # NLP→cron recurring tasks
│       ├── approval_manager.py         # Approval workflows
│       └── sse_broadcaster.py          # Server-sent events
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── components.json                 # shadcn/ui config
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── store/                      # Zustand stores
│   │   │   ├── taskStore.ts
│   │   │   ├── agentStore.ts
│   │   │   ├── projectStore.ts
│   │   │   ├── debateStore.ts
│   │   │   ├── memoryStore.ts
│   │   │   ├── officeStore.ts
│   │   │   ├── productStore.ts
│   │   │   └── settingsStore.ts
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── TaskBoard.tsx
│   │   │   ├── Projects.tsx
│   │   │   ├── ProjectDetail.tsx
│   │   │   ├── DebateRoom.tsx
│   │   │   ├── MemoryMap.tsx
│   │   │   ├── VirtualOffice.tsx
│   │   │   ├── Autopilot.tsx
│   │   │   ├── SkillsHub.tsx
│   │   │   ├── SecurityAudit.tsx
│   │   │   ├── CostDashboard.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── layout/                 # Shell, Sidebar, Header
│   │   │   ├── tasks/                  # KanbanBoard, TaskCard, TaskModal, AgentLiveView
│   │   │   ├── projects/               # ProjectTimeline, ProjectFiles, HandoverView
│   │   │   ├── debate/                 # DebateThread, DebateConclusion, AgentAvatar
│   │   │   ├── memory/                 # MemoryGraph, MemoryNode, TimeSlider
│   │   │   ├── office/                 # OfficeCanvas, AgentSprite, OfficeLayout
│   │   │   ├── autopilot/             # SwipeCard, ResearchPanel, IdeaList
│   │   │   ├── skills/                 # SkillBrowser, SkillCard, SecurityBadge
│   │   │   └── shared/                 # ActivityFeed, CostChart, ApprovalCard
│   │   ├── hooks/
│   │   │   ├── useSSE.ts              # SSE connection + event handling
│   │   │   ├── useGateway.ts          # Gateway status
│   │   │   └── useDebounce.ts
│   │   └── lib/
│   │       ├── api.ts                  # REST client
│   │       ├── utils.ts
│   │       └── constants.ts
├── start.sh
├── pyproject.toml
└── package.json (frontend)
```
