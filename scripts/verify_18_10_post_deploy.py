import json
import re
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


WF_ID = "zVyc6gzToDe5mhc2"
REPORT_PATH = "/root/agent-icerik-sistemi/n8n/18_10_report_20260819.txt"
PENDING_PATH = "/root/agent-icerik-sistemi/site/src/content/_queue/pending.jsonl"
POSTS_DIR = Path("/root/agent-icerik-sistemi/site/src/content/posts")


def sh(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)


def psql_exec(sql: str) -> str:
    # -Atc: tuples-only, unaligned; we parse lines
    return sh(f'docker exec agent-n8n-postgres psql -U n8n -d n8n -Atc "{sql}"')


def parse_cover_and_credit(md_path: Path):
    txt = md_path.read_text(errors="ignore")
    # Look only in frontmatter area
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    if end == -1:
        return {}
    fm = txt[3:end]

    def get_value(key: str) -> str:
        m = re.search(rf"^{re.escape(key)}:\s*(.*)$", fm, flags=re.MULTILINE)
        if not m:
            return ""
        v = m.group(1).strip()
        # strip wrapping quotes
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        return v

    cover = get_value("coverImage")
    photographer = get_value("gorselFotografci")
    photographer_link = get_value("gorselFotografciLink")
    return {
        "coverImage": cover,
        "gorselFotografci": photographer,
        "gorselFotografciLink": photographer_link,
    }


def http_status(url: str) -> str:
    # Use curl to avoid extra dependencies
    # -s: quiet, -o /dev/null: discard body
    return sh(f'curl -s -o /dev/null -w "%{{http_code}}" "{url}"').strip()


def page_check(url: str, cover_url: str):
    # Lightweight HTML substring checks
    # Note: URL might redirect; follow redirects with -L
    html = sh(f'curl -s -L "{url}"').encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    return {
        "page_url": url,
        "contains_coverImage": cover_url in html if cover_url else False,
        "contains_photo_credit": ("Fotoğraf" in html) or ("Foto%C3%A7" in html),
    }


def main():
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    run_at = now.replace(hour=18, minute=20, second=0, microsecond=0)
    if run_at < now:
        run_at = run_at + timedelta(days=1)

    sleep_s = (run_at - now).total_seconds()
    print(f"[verify] Now={now.isoformat()} run_at={run_at.isoformat()} sleep_s={sleep_s:.1f}")
    time.sleep(max(0, sleep_s))

    # Istanbul 18:20 ~= UTC 15:20. Use a bit wider window.
    utc_since = "2026-08-19 15:00:00"
    execs_sql = (
        f'SELECT id, status, "startedAt", "stoppedAt" FROM execution_entity '
        f'WHERE "workflowId" = \'{WF_ID}\' AND "startedAt" > \'{utc_since}\' '
        f'ORDER BY "startedAt" DESC LIMIT 5;'
    )
    execs_txt = psql_exec(execs_sql).strip()
    execs = []
    for line in execs_txt.splitlines() if execs_txt else []:
        parts = line.split("|")
        if len(parts) >= 4:
            execs.append(
                {
                    "id": parts[0],
                    "status": parts[1],
                    "startedAt": parts[2],
                    "stoppedAt": parts[3],
                }
            )

    # Queue lines after cycle
    pending_lines = int(sh(f"wc -l {PENDING_PATH}").split()[0])

    # Detect new post markdown files (last ~6h)
    cutoff = time.time() - 6 * 3600
    candidates = []
    for p in POSTS_DIR.glob("*.md"):
        if p.stat().st_mtime >= cutoff:
            candidates.append(p)
    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    sample = None
    for p in candidates[:12]:
        fm = parse_cover_and_credit(p)
        if fm.get("coverImage"):
            # coverImage might still contain template artifacts; require http(s)
            if "http" in fm["coverImage"]:
                sample = {"post_file": p.name, "post_id": p.stem, **fm}
                break

    cover_ok = None
    page_ok = None
    if sample:
        cover_ok = {"coverImage": sample["coverImage"], "http_status": http_status(sample["coverImage"])}
        post_url = f'https://bilisimpostasi.com.tr/posts/{sample["post_id"]}/'
        page_ok = page_check(post_url, sample["coverImage"])

    # Deploy listener logs (tail)
    try:
        logs = sh(f'journalctl -u agent-icerik-deploy-listener --since "{utc_since}" --no-pager | tail -80')
    except Exception as e:
        logs = f"journalctl failed: {e}"

    out = {
        "workflowId": WF_ID,
        "targetRunAt": run_at.isoformat(),
        "primary_execution": execs[0] if execs else None,
        "executions": execs,
        "queue_lines_after": pending_lines,
        "sample_cover_post": sample,
        "cover_url_check": cover_ok,
        "page_check": page_ok,
        "deploy_listener_logs_tail": logs,
    }

    Path(REPORT_PATH).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[verify] wrote report to {REPORT_PATH}")


if __name__ == "__main__":
    main()

