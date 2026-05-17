"""Native Mission Control runtime schema and seed data."""
import json
import logging
from typing import Iterable

import aiosqlite

logger = logging.getLogger(__name__)


async def _column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        rows = await cursor.fetchall()
    return any(row[1] == column for row in rows)


async def _add_column_if_missing(
    db: aiosqlite.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    if not await _column_exists(db, table, column):
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def _execute_many(db: aiosqlite.Connection, statements: Iterable[str]) -> None:
    for statement in statements:
        await db.execute(statement)


async def ensure_native_runtime_schema(db: aiosqlite.Connection) -> None:
    """Create the local-first runtime tables without depending on OpenClaw."""
    await _execute_many(
        db,
        [
            """
            CREATE TABLE IF NOT EXISTS runtime_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS provider_configs (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                config TEXT NOT NULL DEFAULT '{}',
                last_test_status TEXT,
                last_test_message TEXT,
                last_tested_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS model_configs (
                id TEXT PRIMARY KEY,
                purpose TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL DEFAULT 'openrouter',
                model TEXT NOT NULL,
                routing_policy TEXT NOT NULL DEFAULT 'pinned',
                temperature REAL NOT NULL DEFAULT 0.4,
                max_tokens INTEGER NOT NULL DEFAULT 2048,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
                task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
                title TEXT NOT NULL DEFAULT 'Session',
                status TEXT NOT NULL DEFAULT 'active',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                run_id TEXT,
                agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_calls TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                tokens INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                runtime TEXT NOT NULL DEFAULT 'native',
                run_type TEXT NOT NULL DEFAULT 'agent_message',
                title TEXT NOT NULL,
                objective TEXT NOT NULL DEFAULT '',
                task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
                session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                current_step TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                started_at TEXT,
                completed_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS run_steps (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                step_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                agent_role TEXT DEFAULT '',
                input TEXT NOT NULL DEFAULT '{}',
                output TEXT NOT NULL DEFAULT '{}',
                order_index INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                started_at TEXT,
                completed_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS run_events (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                step_id TEXT REFERENCES run_steps(id) ON DELETE SET NULL,
                event_type TEXT NOT NULL,
                role TEXT DEFAULT '',
                agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                data TEXT NOT NULL DEFAULT '{}',
                sequence INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
                task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
                artifact_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                path TEXT DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tool_registry (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                input_schema TEXT NOT NULL DEFAULT '{}',
                risk_level TEXT NOT NULL DEFAULT 'read-only',
                approval_required INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
        ],
    )

    await db.execute(
        """
        INSERT OR IGNORE INTO runtime_config (key, value)
        VALUES ('active_runtime', 'native')
        """
    )

    # Extend the existing approvals table from the original schema so it can
    # represent native runtime tool approvals.
    try:
        await _add_column_if_missing(db, "approvals", "run_id", "TEXT")
        await _add_column_if_missing(db, "approvals", "tool_name", "TEXT DEFAULT ''")
        await _add_column_if_missing(db, "approvals", "risk_level", "TEXT DEFAULT 'read-only'")
        await _add_column_if_missing(db, "approvals", "request_payload", "TEXT DEFAULT '{}'")
        await _add_column_if_missing(db, "approvals", "decision_payload", "TEXT DEFAULT '{}'")
    except Exception as exc:
        logger.warning("Approval table extension skipped: %s", exc)

    await _seed_model_configs(db)
    await _seed_tool_registry(db)
    await db.commit()


async def _seed_model_configs(db: aiosqlite.Connection) -> None:
    defaults = [
        ("planner", "openrouter/auto", "auto", 0.25, 3000),
        ("builder", "openrouter/auto", "auto", 0.35, 5000),
        ("reviewer", "openrouter/auto", "auto", 0.2, 3000),
        ("cheap_fast", "openrouter/auto", "cheap", 0.3, 1500),
        ("long_context", "openrouter/auto", "strong", 0.25, 8000),
    ]
    for purpose, model, policy, temperature, max_tokens in defaults:
        await db.execute(
            """
            INSERT OR IGNORE INTO model_configs
                (id, purpose, provider, model, routing_policy, temperature, max_tokens)
            VALUES (?, ?, 'openrouter', ?, ?, ?, ?)
            """,
            (f"model-{purpose}", purpose, model, policy, temperature, max_tokens),
        )


async def _seed_tool_registry(db: aiosqlite.Connection) -> None:
    tools = [
        (
            "repo.read",
            "Read repository files and project context.",
            {"type": "object", "properties": {"path": {"type": "string"}}},
            "read-only",
            0,
        ),
        (
            "repo.search",
            "Search repository text and filenames.",
            {"type": "object", "properties": {"query": {"type": "string"}}},
            "read-only",
            0,
        ),
        (
            "repo.draft_patch",
            "Draft a code or documentation patch for human review.",
            {"type": "object", "properties": {"summary": {"type": "string"}}},
            "write",
            1,
        ),
        (
            "tests.run",
            "Run tests or checks and summarize results.",
            {"type": "object", "properties": {"command": {"type": "string"}}},
            "external",
            1,
        ),
        (
            "report.summarize",
            "Summarize a completed run into a durable report.",
            {"type": "object", "properties": {"run_id": {"type": "string"}}},
            "read-only",
            0,
        ),
    ]
    for name, description, schema, risk, approval in tools:
        await db.execute(
            """
            INSERT OR IGNORE INTO tool_registry
                (id, name, description, input_schema, risk_level, approval_required)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"tool-{name}", name, description, json.dumps(schema), risk, approval),
        )
