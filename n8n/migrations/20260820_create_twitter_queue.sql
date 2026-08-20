-- Twitter publish queue for Bilisim Postasi
-- Applied: 2026-08-20

CREATE TABLE IF NOT EXISTS twitter_queue (
  id SERIAL PRIMARY KEY,
  post_slug TEXT NOT NULL,
  post_title TEXT NOT NULL,
  post_summary TEXT,
  post_link TEXT NOT NULL,
  kategori TEXT,
  status TEXT NOT NULL DEFAULT 'pending', -- pending | posted | failed
  scheduled_at TIMESTAMPTZ NOT NULL,
  posted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_twitter_queue_pending_due
  ON twitter_queue (scheduled_at)
  WHERE status = 'pending';
