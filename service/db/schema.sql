-- Инсайдер — Database Schema
-- Applied automatically on bot startup (db.run_migrations).
-- Idempotent — safe to re-run.
--
-- Data isolation: each user (by telegram_id) owns their own:
--   - business_dna (one per user)
--   - interviews (many)
--   - artifacts (many, linked to interviews)
-- No public access — all queries go through the bot backend.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ──────────────────────────────────────────────
-- Users
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    business_dna JSONB,          -- ответы на /init (Company, Domains, Products, etc.)
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Interviews
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    expert_name TEXT,             -- имя эксперта, если не сам пользователь
    expert_role TEXT,
    expert_domain TEXT,
    story JSONB,                  -- STARRI: {situation, task, action, result, relevance, insight}
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'mapped', 'generated')),
    chat_history JSONB,           -- полный лог диалога (для контекста)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_interviews_user_id') THEN
        CREATE INDEX idx_interviews_user_id ON interviews(user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_interviews_status') THEN
        CREATE INDEX idx_interviews_status ON interviews(status);
    END IF;
END $$;

-- ──────────────────────────────────────────────
-- Artifacts (generated content)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    audience_id TEXT NOT NULL,     -- b2g / b2b / b2c
    format_id TEXT NOT NULL,       -- telegram_post / talk_proposal / case_study
    angle_id TEXT NOT NULL,        -- result / problem / insight / technical
    content TEXT NOT NULL,          -- сгенерированный текст
    preview TEXT,                  -- первые 200 символов
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_artifacts_user_id') THEN
        CREATE INDEX idx_artifacts_user_id ON artifacts(user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_artifacts_interview_id') THEN
        CREATE INDEX idx_artifacts_interview_id ON artifacts(interview_id);
    END IF;
END $$;

-- ──────────────────────────────────────────────
-- Session State (текущий шаг пользователя в боте)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_state (
    user_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    current_command TEXT NOT NULL DEFAULT 'idle', -- idle / init / extract_s / extract_t / ... / map / generate
    interview_id UUID REFERENCES interviews(id) ON DELETE SET NULL,
    context JSONB,                -- временные данные текущего шага
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- Conversation Log (вся переписка пользователей)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot', 'system')),
    text TEXT NOT NULL,
    command TEXT,                  -- current_command на момент сообщения
    created_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_conversation_log_user') THEN
        CREATE INDEX idx_conversation_log_user ON conversation_log(user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_conversation_log_created') THEN
        CREATE INDEX idx_conversation_log_created ON conversation_log(created_at);
    END IF;
END $$;