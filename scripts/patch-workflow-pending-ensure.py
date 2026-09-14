#!/usr/bin/env python3
"""Prepend pending.jsonl ensure (executeCommand) before first queue read."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

CMD = (
    "mkdir -p /home/node/site/src/content/_queue && "
    "touch /home/node/site/src/content/_queue/pending.jsonl"
)
ENSURE_NAME = "Kuyruk Dosyasini Garantile"


def load_wf(path: Path) -> dict:
    data = json.loads(path.read_text())
    return data[0] if isinstance(data, list) else data


def patch(wf: dict, *, from_node: str, to_node: str) -> dict:
    nodes_by_name = {n["name"]: n for n in wf["nodes"]}
    src = nodes_by_name[from_node]
    dst = nodes_by_name[to_node]
    ensure_pos = [
        int((src["position"][0] + dst["position"][0]) / 2),
        src["position"][1],
    ]
    ensure = {
        "parameters": {"command": CMD},
        "type": "n8n-nodes-base.executeCommand",
        "typeVersion": 1,
        "position": ensure_pos,
        "id": str(uuid4()),
        "name": ENSURE_NAME,
        "onError": "continueRegularOutput",
    }
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != ENSURE_NAME]
    wf["nodes"].append(ensure)
    wf["connections"][from_node] = {
        "main": [[{"node": ENSURE_NAME, "type": "main", "index": 0}]]
    }
    wf["connections"][ENSURE_NAME] = {
        "main": [[{"node": to_node, "type": "main", "index": 0}]]
    }
    return wf


def main() -> None:
    root = Path("/root/agent-icerik-sistemi/n8n/backups")
    publish_in = sorted(root.glob("haber-yayinlama-toplu-*-pre-pending-ensure.json"))[-1]
    collect_in = sorted(root.glob("haber-toplama-*-pre-pending-ensure.json"))[-1]

    pub = load_wf(publish_in)
    patch(pub, from_node="Zamanlayici", to_node="Kuyrugu Oku")
    pub["active"] = True
    pub_out = root / "haber-yayinlama-toplu-pending-ensure-patched.json"
    pub_out.write_text(json.dumps(pub, ensure_ascii=False, indent=2))
    print("wrote", pub_out)

    col = load_wf(collect_in)
    patch(col, from_node="Edit Fields2", to_node="Read/Write Files from Disk1")
    col["active"] = True
    col_out = root / "haber-toplama-pending-ensure-patched.json"
    col_out.write_text(json.dumps(col, ensure_ascii=False, indent=2))
    print("wrote", col_out)


if __name__ == "__main__":
    main()
