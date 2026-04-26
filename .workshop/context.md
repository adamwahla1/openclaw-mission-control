# OpenClaw Mission Control

## Context
Building the definitive Mission Control for OpenClaw — best-of-breed agent orchestration dashboard.

## Architecture
- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS + shadcn/ui + Zustand
- **Backend**: FastAPI (Python) with SQLite (WAL mode)
- **All AI/Models**: OpenClaw Gateway — no direct provider calls
- **Real-time**: WebSocket (backend ↔ OC Gateway) + SSE (frontend ← backend)
- **Build phases**: Phase 1 (Foundation+Tasks), Phase 2 (Projects+Debate), Phase 3 (Memory+Office), Phase 4 (Autopilot+Skills)

## Key Patterns
- Backend acts as `operator` role WS client to OC Gateway
- Bidirectional sync with OC — agents, sessions, skills, memories all synced
- MC SQLite stores UI state, projects, debates, local aggregations
- OC Gateway is source of truth for agents, sessions, execution
- Intelligent Agent Factory: research → SOUL construction → skill injection → validation

## Design
- Apple design guidelines — clean, dark-first theme
- Isomorphic 2D office visualization on HTML5 Canvas
- D3.js neural memory graph
- Kanban board with drag-and-drop