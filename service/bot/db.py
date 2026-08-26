"""Database layer for Инсайдер Service.
Uses asyncpg with a connection pool. All queries go through this module.
"""

import os
import pathlib
import json
import asyncpg
import logging
from typing import Optional

_pool: Optional[asyncpg.Pool] = None
logger = logging.getLogger(__name__)

# Path to schema file
_SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "db" / "schema.sql"


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register JSONB codec so all jsonb columns return as Python dicts/lists."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool(dsn: str | None = None) -> asyncpg.Pool:
    """Initialize the connection pool. Call once at startup."""
    global _pool
    dsn = dsn or os.environ["DATABASE_URL"]
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, init=_init_connection)
    return _pool


async def run_migrations() -> None:
    """Apply schema.sql to the database. Idempotent — safe to re-run."""
    pool = _pool_required()
    sql = _SCHEMA_PATH.read_text()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("Database migrations applied successfully")


async def close_pool() -> None:
    """Close the connection pool. Call at shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _pool_required() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


def _maybe_json(value):
    """Casts a JSONB value to Python dict/list if it came back as a string.

    asyncpg returns jsonb columns as raw strings unless a codec is registered.
    This helper makes the code safe regardless of codec state.
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _decode_row(row: dict, *json_fields: str) -> dict:
    """Decode specific jsonb fields of a row dict in place."""
    for field in json_fields:
        if row.get(field) is not None:
            row[field] = _maybe_json(row[field])
    return row


# ── Users ──────────────────────────────────────────────

async def upsert_user(
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> dict:
    pool = _pool_required()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id)
            DO UPDATE SET username = COALESCE($2, users.username),
                           first_name = COALESCE($3, users.first_name),
                           last_name = COALESCE($4, users.last_name),
                           updated_at = NOW()
            RETURNING *
            """,
            telegram_id, username, first_name, last_name,
        )
        return _decode_row(dict(row), "business_dna")


async def get_user(telegram_id: int) -> dict | None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        return _decode_row(dict(row), "business_dna") if row else None


async def update_business_dna(telegram_id: int, dna: dict) -> None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET business_dna = $1::jsonb, updated_at = NOW() WHERE telegram_id = $2",
            json.dumps(dna), telegram_id,
        )


# ── Interviews ─────────────────────────────────────────

async def create_interview(user_id: int) -> dict:
    pool = _pool_required()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO interviews (user_id) VALUES ($1) RETURNING *",
            user_id,
        )
        return _decode_row(dict(row), "story", "chat_history")


async def get_interview(interview_id: str) -> dict | None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM interviews WHERE id = $1", interview_id
        )
        return _decode_row(dict(row), "story", "chat_history") if row else None


async def get_user_interviews(user_id: int, limit: int = 10) -> list[dict]:
    pool = _pool_required()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM interviews WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit,
        )
        return [_decode_row(dict(r), "story", "chat_history") for r in rows]


async def update_story(interview_id: str, story: dict, chat_history: list | None = None) -> None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE interviews SET story = $1::jsonb, status = 'draft', chat_history = $2::jsonb, updated_at = NOW() WHERE id = $3",
            json.dumps(story), json.dumps(chat_history) if chat_history else None, interview_id,
        )


async def update_interview_status(interview_id: str, status: str) -> None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE interviews SET status = $1, updated_at = NOW() WHERE id = $2",
            status, interview_id,
        )


async def update_interview_expert(interview_id: str, expert_name: str, expert_role: str, expert_domain: str) -> None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE interviews SET expert_name = $1, expert_role = $2, expert_domain = $3, updated_at = NOW() WHERE id = $4",
            expert_name, expert_role, expert_domain, interview_id,
        )


# ── Artifacts ──────────────────────────────────────────

async def create_artifact(
    interview_id: str,
    user_id: int,
    audience_id: str,
    format_id: str,
    angle_id: str,
    content: str,
) -> dict:
    pool = _pool_required()
    preview = content[:200]
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO artifacts (interview_id, user_id, audience_id, format_id, angle_id, content, preview)
            VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *
            """,
            interview_id, user_id, audience_id, format_id, angle_id, content, preview,
        )
        return dict(row)


async def get_user_artifacts(user_id: int, limit: int = 10) -> list[dict]:
    pool = _pool_required()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM artifacts WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit,
        )
        return [dict(r) for r in rows]


# ── Session State ──────────────────────────────────────

async def set_session_state(user_id: int, command: str, interview_id: str | None = None, context: dict | None = None) -> None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO session_state (user_id, current_command, interview_id, context, updated_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET current_command = $2, interview_id = COALESCE($3, session_state.interview_id),
                           context = $4::jsonb, updated_at = NOW()
            """,
            user_id, command, interview_id, json.dumps(context) if context else None,
        )


async def get_session_state(user_id: int) -> dict | None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM session_state WHERE user_id = $1", user_id
        )
        return _decode_row(dict(row), "context") if row else None


async def clear_session_state(user_id: int) -> None:
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE session_state SET current_command = 'idle', context = NULL, updated_at = NOW() WHERE user_id = $1",
            user_id,
        )


# ── Conversation Log ─────────────────────────────

async def log_conversation(
    user_id: int,
    role: str,
    text: str,
    command: str | None = None,
) -> None:
    """Log a single message (user or bot) to conversation_log table."""
    pool = _pool_required()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO conversation_log (user_id, role, text, command) VALUES ($1, $2, $3, $4)",
            user_id, role, text, command,
        )


async def get_conversation_logs(
    user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Fetch conversation logs, optionally filtered by user. Newest first."""
    pool = _pool_required()
    async with pool.acquire() as conn:
        if user_id is not None:
            rows = await conn.fetch(
                "SELECT * FROM conversation_log WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                user_id, limit, offset,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM conversation_log ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
        return [dict(r) for r in rows]


async def get_conversation_stats() -> dict:
    """Get stats about all conversations."""
    pool = _pool_required()
    async with pool.acquire() as conn:
        total_msgs = await conn.fetchval("SELECT COUNT(*) FROM conversation_log")
        total_users = await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM conversation_log")
        last_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM conversation_log WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        user_breakdown = await conn.fetch(
            """
            SELECT u.telegram_id, u.username, u.first_name,
                   COUNT(cl.id) AS msg_count, MAX(cl.created_at) AS last_msg
            FROM conversation_log cl
            JOIN users u ON u.telegram_id = cl.user_id
            GROUP BY u.telegram_id
            ORDER BY last_msg DESC
            """
        )
        return {
            "total_messages": total_msgs,
            "total_users": total_users,
            "last_24h": last_24h,
            "users": [dict(r) for r in user_breakdown],
        }