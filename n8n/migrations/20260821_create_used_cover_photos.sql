-- Cover photo cooldown (7-day reuse block) for Bilisim Postasi
-- Applied: 2026-08-21

CREATE TABLE IF NOT EXISTS used_cover_photos (
  id SERIAL PRIMARY KEY,
  unsplash_photo_id TEXT NOT NULL,
  photo_url TEXT NOT NULL,
  used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  post_slug TEXT
);

CREATE INDEX IF NOT EXISTS idx_used_cover_photos_photo_id
  ON used_cover_photos (unsplash_photo_id);

CREATE INDEX IF NOT EXISTS idx_used_cover_photos_used_at
  ON used_cover_photos (used_at);
