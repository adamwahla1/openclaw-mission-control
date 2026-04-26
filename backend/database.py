"""SQLite database with WAL mode and migration support."""
import aiosqlite
import os
import logging
from config import settings

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.execute("PRAGMA busy_timeout=5000")
        await run_migrations(_db)
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


MIGRATIONS = [
    # Migration 0: Core tables
    """
    -- Tasks
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'inbox',
        priority TEXT NOT NULL DEFAULT 'medium',
        board_id TEXT,
        project_id TEXT,
        assigned_agent_id TEXT,
        parent_task_id TEXT,
        gateway_session_id TEXT,
        template_id TEXT,
        cron_expression TEXT,
        is_template INTEGER DEFAULT 0,
        tags TEXT DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Agents (MC-side metadata; source of truth is OpenClaw Gateway)
    CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        gateway_agent_id TEXT,
        name TEXT NOT NULL,
        role TEXT DEFAULT '',
        soul_config TEXT DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'idle',
        trust_score REAL DEFAULT 50.0,
        parent_orchestrator_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Agent skills
    CREATE TABLE IF NOT EXISTS agent_skills (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        prompt_template TEXT DEFAULT '',
        confidence_score REAL DEFAULT 0.5,
        use_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        skill_source TEXT DEFAULT 'internal',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Task messages (mirrors gateway session messages)
    CREATE TABLE IF NOT EXISTS task_messages (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        agent_id TEXT,
        content TEXT NOT NULL,
        message_type TEXT DEFAULT 'assistant',
        tool_calls TEXT DEFAULT '[]',
        parent_message_id TEXT,
        round_number INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Task comments
    CREATE TABLE IF NOT EXISTS task_comments (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        author_type TEXT NOT NULL DEFAULT 'user',
        author_id TEXT,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Task attachments
    CREATE TABLE IF NOT EXISTS task_attachments (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        mime_type TEXT DEFAULT '',
        size INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Task checkpoints
    CREATE TABLE IF NOT EXISTS task_checkpoints (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        agent_id TEXT,
        checkpoint_data TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Task sessions (links tasks to OpenClaw sessions)
    CREATE TABLE IF NOT EXISTS task_sessions (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        agent_id TEXT,
        gateway_session_id TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Projects
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT DEFAULT 'active',
        auto_detected INTEGER DEFAULT 0,
        detection_method TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS project_tasks (
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        PRIMARY KEY (project_id, task_id)
    );

    CREATE TABLE IF NOT EXISTS project_files (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        task_id TEXT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        file_type TEXT DEFAULT '',
        pinned INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS project_handovers (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        task_id TEXT,
        content_md TEXT DEFAULT '',
        summary TEXT DEFAULT '',
        key_decisions TEXT DEFAULT '[]',
        open_questions TEXT DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Debates
    CREATE TABLE IF NOT EXISTS debates (
        id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        current_round INTEGER DEFAULT 0,
        max_rounds INTEGER DEFAULT 5,
        conclusion_md TEXT,
        needs_user_input INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS debate_participants (
        id TEXT PRIMARY KEY,
        debate_id TEXT NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
        agent_id TEXT NOT NULL,
        role TEXT DEFAULT '',
        specialty TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS debate_messages (
        id TEXT PRIMARY KEY,
        debate_id TEXT NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
        agent_id TEXT,
        round_number INTEGER DEFAULT 0,
        content TEXT NOT NULL,
        response_to_id TEXT,
        stance TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS debate_questions (
        id TEXT PRIMARY KEY,
        debate_id TEXT NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
        question TEXT NOT NULL,
        asked_by_agent_id TEXT,
        user_response TEXT,
        answered_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Memories
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        agent_id TEXT,
        content TEXT NOT NULL,
        memory_type TEXT DEFAULT 'fact',
        importance REAL DEFAULT 0.5,
        access_count INTEGER DEFAULT 0,
        tags TEXT DEFAULT '[]',
        source_type TEXT,
        source_id TEXT,
        last_accessed TEXT,
        decayed INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS memory_links (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        link_type TEXT DEFAULT 'related',
        strength REAL DEFAULT 0.5,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Cost tracking
    CREATE TABLE IF NOT EXISTS cost_entries (
        id TEXT PRIMARY KEY,
        task_id TEXT,
        agent_id TEXT,
        model TEXT DEFAULT '',
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        session_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS budget_caps (
        id TEXT PRIMARY KEY,
        scope TEXT NOT NULL,
        scope_id TEXT,
        period TEXT NOT NULL DEFAULT 'monthly',
        cap_usd REAL NOT NULL,
        current_usd REAL DEFAULT 0.0,
        paused INTEGER DEFAULT 0
    );

    -- Security events
    CREATE TABLE IF NOT EXISTS security_events (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        agent_id TEXT,
        severity TEXT DEFAULT 'info',
        details TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Activity log
    CREATE TABLE IF NOT EXISTS activities (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        actor_type TEXT DEFAULT '',
        actor_id TEXT DEFAULT '',
        target_type TEXT DEFAULT '',
        target_id TEXT DEFAULT '',
        details TEXT DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Approvals
    CREATE TABLE IF NOT EXISTS approvals (
        id TEXT PRIMARY KEY,
        action_type TEXT NOT NULL,
        target_type TEXT DEFAULT '',
        target_id TEXT DEFAULT '',
        requested_by TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        reviewer_notes TEXT DEFAULT '',
        decided_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Webhooks
    CREATE TABLE IF NOT EXISTS webhooks (
        id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        events TEXT DEFAULT '[]',
        secret_hash TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS webhook_deliveries (
        id TEXT PRIMARY KEY,
        webhook_id TEXT NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
        event TEXT NOT NULL,
        payload TEXT DEFAULT '{}',
        status_code INTEGER,
        attempt INTEGER DEFAULT 1,
        delivered_at TEXT
    );

    -- Skills registry
    CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        skill_source TEXT DEFAULT 'internal',
        registry_slug TEXT,
        content TEXT DEFAULT '',
        security_scan_result TEXT DEFAULT '{}',
        installed INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Products (Autopilot)
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        repo_url TEXT DEFAULT '',
        live_url TEXT DEFAULT '',
        product_program_md TEXT DEFAULT '',
        status TEXT DEFAULT 'active',
        automation_tier TEXT DEFAULT 'supervised',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Schema version tracking
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
    );
    INSERT OR IGNORE INTO schema_version (version) VALUES (1);
    """,
    # Migration 2: Extend task_messages for orchestrator
    """
    ALTER TABLE task_messages ADD COLUMN session_id TEXT;
    ALTER TABLE task_messages ADD COLUMN role TEXT DEFAULT 'assistant';
    ALTER TABLE task_messages ADD COLUMN agent_name TEXT;
    ALTER TABLE task_messages ADD COLUMN tokens INTEGER;
    INSERT OR REPLACE INTO schema_version (version) VALUES (2);
    """,
]


async def run_migrations(db: aiosqlite.Connection):
    """Run pending migrations."""
    # Check current version
    try:
        async with db.execute("SELECT MAX(version) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            current = row[0] if row and row[0] else 0
    except Exception:
        current = 0

    for i, sql in enumerate(MIGRATIONS):
        version = i + 1
        if version > current:
            logger.info(f"Running migration {version}...")
            # Strip SQL comments before splitting on semicolons
            lines = []
            for line in sql.split('\n'):
                stripped = line.strip()
                if stripped.startswith('--'):
                    continue
                lines.append(line)
            clean_sql = '\n'.join(lines)
            for statement in clean_sql.split(';'):
                statement = statement.strip()
                if statement:
                    await db.execute(statement)
            await db.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (version,),
            )
            await db.commit()
            logger.info(f"Migration {version} complete")
