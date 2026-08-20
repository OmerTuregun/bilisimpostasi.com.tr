#!/usr/bin/env python3
"""Send recovery notifications for exec #509 posts. Does NOT touch twitter_queue."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/root/agent-icerik-sistemi")
POSTS_DIR = ROOT / "site/src/content/posts/tr"
ENV_PATH = ROOT / "n8n/.env"
SUBSCRIBERS_PATH = ROOT / "n8n/data/telegram-subscribers.jsonl"
RESULTS_PATH = ROOT / "n8n/backups/exec509-notify-results.json"
EMAIL_WEBHOOK = "https://n8n.omerfarukturegun.com.tr/webhook/haber-email-notify"
SITE_BASE = "https://bilisimpostasi.com.tr/posts"
ADMIN_CHAT_ID = "6675249884"
DELAY_SEC = 2.5
GLOB = "*20260820-12*.md"
SKIP_MARKERS = ("İtfaiyeci", "Itfaiyeci", "itfaiyeci")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip()] = val.strip().strip('"')
    return data


def truncate_desc(desc: str, limit: int = 150) -> str:
    desc = (desc or "").strip()
    if len(desc) <= limit:
        return desc
    cut = desc[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def should_skip(path: Path, meta: dict[str, str], body: str) -> str | None:
    title = meta.get("title", "")
    for m in SKIP_MARKERS:
        if m in title or m in body[:500]:
            return f"skip marker: {m}"
    # truncated heuristic: very short body or title ends oddly mid-word with ellipsis only in body start
    body_text = body.strip()
    if len(body_text) < 80:
        return "truncated body"
    return None


def telegram_send(token: str, chat_id: str | int, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "http_status": resp.status, "body": raw[:500]}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "http_status": e.code, "body": err_body}
    except Exception as e:
        return {"ok": False, "http_status": None, "body": str(e)[:500]}


def email_send(text: str, post_count: int) -> dict:
    payload = json.dumps({"text": text, "post_count": post_count}).encode("utf-8")
    req = urllib.request.Request(
        EMAIL_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "http_status": resp.status, "body": raw[:800]}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:800]
        return {"ok": False, "http_status": e.code, "body": err_body}
    except Exception as e:
        return {"ok": False, "http_status": None, "body": str(e)[:800]}


def load_subscribers(path: Path) -> list[int]:
    ids: list[int] = []
    if not path.exists():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            ids.append(int(obj["chat_id"]))
        except Exception:
            continue
    return ids


def admin_message(title: str, description: str, slug: str) -> str:
    desc = truncate_desc(description, 150)
    return (
        "📰 Yeni yazı yayınlandı!\n\n"
        f"{title}\n\n"
        f"{desc}\n\n"
        f"Habere gitmek için: {SITE_BASE}/{slug}/"
    )


def main() -> int:
    t0 = time.time()
    env = load_env(ENV_PATH)
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    admin_id = env.get("TELEGRAM_CHAT_ID", ADMIN_CHAT_ID) or ADMIN_CHAT_ID
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN missing", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob(GLOB), key=lambda p: p.name)
    posts: list[dict] = []
    skipped: list[dict] = []

    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(raw)
        body = raw
        if raw.startswith("---"):
            end = raw.find("\n---", 3)
            if end >= 0:
                body = raw[end + 4 :]
        reason = should_skip(path, meta, body)
        slug = path.name[:-3] if path.name.endswith(".md") else path.stem
        if reason:
            skipped.append({"file": path.name, "reason": reason})
            continue
        posts.append(
            {
                "file": path.name,
                "slug": slug,
                "title": meta.get("title", slug),
                "description": meta.get("description", ""),
            }
        )

    # Sort by slug timestamp suffix for stable order
    posts.sort(key=lambda p: p["slug"])

    results: dict = {
        "execution": 509,
        "posts_found": len(files),
        "posts_used": len(posts),
        "skipped": skipped,
        "admin_messages": [],
        "subscriber_digests": [],
        "email": None,
        "sample_admin_message": None,
        "digest_text": None,
        "elapsed_seconds": None,
        "counts": {},
        "verifications": {},
    }

    # 1) Admin per-post
    for i, post in enumerate(posts):
        text = admin_message(post["title"], post["description"], post["slug"])
        if results["sample_admin_message"] is None:
            results["sample_admin_message"] = text
        r = telegram_send(token, admin_id, text)
        results["admin_messages"].append(
            {
                "slug": post["slug"],
                "title": post["title"],
                "ok": r["ok"],
                "http_status": r["http_status"],
                "error_sample": None if r["ok"] else r["body"],
            }
        )
        if i < len(posts) - 1 or True:
            # always delay between telegram calls; last admin still delays before digest
            time.sleep(DELAY_SEC)

    # 2) Subscriber digest
    digest_lines = ["🆕 Yeni yazılar:", ""]
    for idx, post in enumerate(posts, 1):
        digest_lines.append(
            f"{idx}. {post['title']} - {SITE_BASE}/{post['slug']}/"
        )
    digest_text = "\n".join(digest_lines)
    results["digest_text"] = digest_text

    subscribers = load_subscribers(SUBSCRIBERS_PATH)
    if not subscribers:
        # fallback: still send digest to admin as normal flow would
        subscribers = [int(admin_id)]

    for i, chat_id in enumerate(subscribers):
        r = telegram_send(token, chat_id, digest_text)
        results["subscriber_digests"].append(
            {
                "chat_id": chat_id,
                "ok": r["ok"],
                "http_status": r["http_status"],
                "error_sample": None if r["ok"] else r["body"],
            }
        )
        time.sleep(DELAY_SEC)

    # 3) Email webhook once
    email_text = "\n".join(
        f"{idx}. {post['title']} - {SITE_BASE}/{post['slug']}/"
        for idx, post in enumerate(posts, 1)
    )
    email_r = email_send(email_text, len(posts))
    results["email"] = {
        "ok": email_r["ok"],
        "http_status": email_r["http_status"],
        "response_sample": email_r["body"],
        "post_count": len(posts),
    }

    admin_ok = sum(1 for m in results["admin_messages"] if m["ok"])
    sub_ok = sum(1 for m in results["subscriber_digests"] if m["ok"])
    tg_ok = admin_ok + sub_ok
    tg_total = len(results["admin_messages"]) + len(results["subscriber_digests"])

    sample = results["sample_admin_message"] or ""
    # body paragraphs check: look for known long body sentence fragments
    body_markers = [
        "Yapay zeka ajanlarının kurumsal",
        "Kurumsal dünyada yapay zeka modellerinin",
        "Eğitim alanında yapay zeka kullanımı",
    ]
    has_full_body = any(m in sample for m in body_markers)
    has_correct_link = "https://bilisimpostasi.com.tr/posts/" in sample
    digest_links_ok = all(
        f"https://bilisimpostasi.com.tr/posts/{p['slug']}/" in digest_text for p in posts
    )

    results["counts"] = {
        "admin_ok": admin_ok,
        "admin_total": len(results["admin_messages"]),
        "subscriber_ok": sub_ok,
        "subscriber_total": len(results["subscriber_digests"]),
        "telegram_ok": tg_ok,
        "telegram_total": tg_total,
        "email_ok": 1 if email_r["ok"] else 0,
        "post_count": len(posts),
    }
    results["verifications"] = {
        "sample_admin_is_short_format": (not has_full_body)
        and "📰 Yeni yazı yayınlandı!" in sample
        and "Habere gitmek için:" in sample,
        "sample_has_full_article_body": has_full_body,
        "sample_link_correct": has_correct_link,
        "digest_links_correct": digest_links_ok,
        "email_http_status": email_r["http_status"],
    }
    results["elapsed_seconds"] = round(time.time() - t0, 2)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Safe summary to stdout (no secrets)
    print(
        json.dumps(
            {
                "results_path": str(RESULTS_PATH),
                "counts": results["counts"],
                "verifications": results["verifications"],
                "email_http_status": email_r["http_status"],
                "elapsed_seconds": results["elapsed_seconds"],
                "skipped": skipped,
                "sample_admin_preview": (sample[:200] + "…") if len(sample) > 200 else sample,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if tg_ok == tg_total and email_r["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
