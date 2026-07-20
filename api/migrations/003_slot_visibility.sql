-- 003_slot_visibility.sql — instructor can hide slots; admin always sees all

ALTER TABLE slots
    ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS slots_hidden_idx ON slots (is_hidden) WHERE is_hidden = TRUE;

COMMENT ON COLUMN slots.is_hidden IS
  'Instructor-hidden: not offered to students; still visible to admin in view mode.';
