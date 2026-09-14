-- Aşama 49: unified notify queue (Telegram + Email), Twitter-style retry
-- Applied: 2026-08-26

CREATE TABLE IF NOT EXISTS notify_queue (
  id SERIAL PRIMARY KEY,
  channel TEXT NOT NULL, -- telegram_owner | telegram_subscriber | email_digest | contact_form
  payload JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending | sent | failed
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT,
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notify_queue_pending_due
  ON notify_queue (scheduled_at)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_notify_queue_channel_status
  ON notify_queue (channel, status);
