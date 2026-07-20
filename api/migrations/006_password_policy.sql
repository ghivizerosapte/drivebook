-- 006_password_policy.sql — force password change on first login

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN users.must_change_password IS
  'When TRUE, client must call POST /v1/auth/change-password before using the app.';
