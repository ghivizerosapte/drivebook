-- 004_auth_and_audit.sql — auth, roles, audit log, hide requests, moderation

-- Users: admin, supervisor, instructors (drivers)
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- argon2id
    role          TEXT NOT NULL CHECK (role IN ('admin','supervisor','instructor')),
    instructor_id INTEGER REFERENCES instructors(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login    TIMESTAMPTZ
);

COMMENT ON TABLE users IS 'Admin, supervisor, and instructor login accounts.';

-- Session tokens (JWT-like opaque strings stored for audit + revocation)
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip          INET,
    user_agent  TEXT
);
CREATE INDEX sessions_user ON sessions (user_id, expires_at DESC);

-- Audit log: every action in the system
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    action      TEXT NOT NULL,              -- 'login', 'hide_request', 'hide_accept', 'hide_reject', 'booking', 'admin_view', etc.
    target_type TEXT,                       -- 'slot', 'user', 'instructor'
    target_id   INTEGER,
    details     JSONB DEFAULT '{}'::jsonb,  -- free-form details (reason, ip, etc.)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_created ON audit_log (created_at DESC);
CREATE INDEX audit_user ON audit_log (user_id, created_at DESC);

-- Hide requests: instructors request to hide slots with a reason
CREATE TABLE IF NOT EXISTS hide_requests (
    id           SERIAL PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    reason       TEXT NOT NULL,            -- driver's explanation
    scope        JSONB NOT NULL DEFAULT '{}',  -- {slot_ids:[], hide_from:'18:00', date_from, date_to}
    status       TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','accepted','rejected')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at  TIMESTAMPTZ,
    reviewed_by  INTEGER REFERENCES users(id)
);
CREATE INDEX hide_status ON hide_requests (status, created_at);

-- Notification badge counter (denormalized, recalculated on read)
-- We use a simple approach: count in API, store nothing persistent.
