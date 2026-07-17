-- 002_v2.sql — waitlist, events, schools, reminders, rate limits, calendar helpers

CREATE TABLE IF NOT EXISTS schools (
    slug                  TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    default_lang          TEXT NOT NULL DEFAULT 'ro',
    deposit_required      BOOLEAN NOT NULL DEFAULT FALSE,
    deposit_amount_cents  INT NOT NULL DEFAULT 0 CHECK (deposit_amount_cents >= 0),
    grace_minutes         INT NOT NULL DEFAULT 15 CHECK (grace_minutes >= 0),
    slot_minutes          INT NOT NULL DEFAULT 90 CHECK (slot_minutes > 0),
    admin_password_hash   TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schools (slug, name, default_lang, deposit_required, grace_minutes, slot_minutes)
VALUES ('chisinau', 'DriveBook Chișinău', 'ro', FALSE, 15, 90)
ON CONFLICT (slug) DO NOTHING;

ALTER TABLE slots
    ADD COLUMN IF NOT EXISTS held_until TIMESTAMPTZ;

ALTER TABLE bookings
    ADD COLUMN IF NOT EXISTS channel TEXT,
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reminder_24h_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reminder_2h_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancel_token TEXT;

-- backfill channel from source
UPDATE bookings SET channel = source WHERE channel IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS bookings_cancel_token_uq
    ON bookings (cancel_token) WHERE cancel_token IS NOT NULL;

CREATE TABLE IF NOT EXISTS waitlist (
    id                   BIGSERIAL PRIMARY KEY,
    instructor_id        BIGINT REFERENCES instructors(id),
    preferred_starts_at  TIMESTAMPTZ,
    preferred_ends_at    TIMESTAMPTZ,
    zone                 TEXT,
    student_name         TEXT NOT NULL,
    student_phone        TEXT NOT NULL,
    lang                 TEXT NOT NULL DEFAULT 'ro',
    source               TEXT NOT NULL DEFAULT 'site',
    status               TEXT NOT NULL DEFAULT 'open'
                         CHECK (status IN ('open', 'notified', 'booked', 'cancelled')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS waitlist_open_idx ON waitlist (status, created_at)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    event_type   TEXT NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'unknown',
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    booking_id   BIGINT REFERENCES bookings(id),
    slot_id      BIGINT REFERENCES slots(id),
    ip           TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_type_created_idx ON events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS events_channel_idx ON events (channel, created_at DESC);

CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket_key    TEXT PRIMARY KEY,
    window_start  TIMESTAMPTZ NOT NULL,
    count         INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS webhook_log (
    id           BIGSERIAL PRIMARY KEY,
    channel      TEXT NOT NULL,
    direction    TEXT NOT NULL DEFAULT 'in',
    payload      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache_meta (
    cache_key    TEXT PRIMARY KEY,
    invalidated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
