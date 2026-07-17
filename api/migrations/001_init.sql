-- 001_init.sql — DriveBook core schema
-- Chișinău-only driving school booking module

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE instructors (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    district        TEXT NOT NULL,
    car             TEXT NOT NULL,
    transmission    TEXT NOT NULL CHECK (transmission IN ('manual', 'automatic', 'both')),
    experience_years INT NOT NULL CHECK (experience_years >= 0),
    rating          NUMERIC(3,2) NOT NULL DEFAULT 4.80
                    CHECK (rating >= 0 AND rating <= 5),
    languages       TEXT NOT NULL DEFAULT 'ro,ru',
    bio             TEXT NOT NULL DEFAULT '',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE slots (
    id              BIGSERIAL PRIMARY KEY,
    instructor_id   BIGINT NOT NULL REFERENCES instructors(id),
    starts_at       TIMESTAMPTZ NOT NULL,
    ends_at         TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'held', 'booked', 'cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT slots_time_ok CHECK (ends_at > starts_at),
    CONSTRAINT slots_instructor_start_uq UNIQUE (instructor_id, starts_at)
);

CREATE INDEX slots_status_starts_idx ON slots (status, starts_at);
CREATE INDEX slots_instructor_starts_idx ON slots (instructor_id, starts_at);

CREATE TABLE bookings (
    id                  BIGSERIAL PRIMARY KEY,
    slot_id             BIGINT NOT NULL REFERENCES slots(id),
    student_name        TEXT NOT NULL,
    student_phone       TEXT NOT NULL,
    student_email       TEXT,
    lesson_type         TEXT NOT NULL DEFAULT 'standard',
    source              TEXT NOT NULL DEFAULT 'site',
    lang                TEXT NOT NULL DEFAULT 'ro' CHECK (lang IN ('ro', 'ru', 'en')),
    notes               TEXT,
    status              TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('pending_deposit', 'confirmed', 'cancelled', 'completed')),
    deposit_amount_cents INT NOT NULL DEFAULT 0 CHECK (deposit_amount_cents >= 0),
    deposit_status      TEXT NOT NULL DEFAULT 'none'
                        CHECK (deposit_status IN ('none', 'pending', 'paid', 'waived')),
    idempotency_key     TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- second line of defence against double booking the same slot
    CONSTRAINT bookings_slot_uq UNIQUE (slot_id),
    CONSTRAINT bookings_idem_uq UNIQUE (idempotency_key)
);

CREATE INDEX bookings_created_idx ON bookings (created_at DESC);
CREATE INDEX bookings_phone_idx ON bookings (student_phone);

-- Durable idempotent response store (full HTTP replay)
CREATE TABLE idempotency_records (
    key             TEXT PRIMARY KEY,
    request_hash    TEXT NOT NULL,
    status_code     INT NOT NULL,
    response_body   JSONB NOT NULL,
    booking_id      BIGINT REFERENCES bookings(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- schema_migrations is owned by the migrate runner (CREATE IF NOT EXISTS there).