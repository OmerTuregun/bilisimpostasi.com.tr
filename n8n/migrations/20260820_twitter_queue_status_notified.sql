-- twitter_queue status values: pending | notified | failed
-- (legacy rows may still have posted)
-- Applied: 2026-08-20 — semi-automatic ntfy push replaces X API posting

COMMENT ON COLUMN twitter_queue.status IS 'pending: queued; notified: ntfy push sent; failed: notify error; posted: legacy X API';
