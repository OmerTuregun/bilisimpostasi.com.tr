#!/usr/bin/env python3
"""Update Haber Yayınlama (Toplu) workflow with deploy-before-telegram flow."""

from __future__ import annotations

import json
import subprocess
import uuid

WORKFLOW_NAME = "Haber Yayınlama (Toplu)"


def new_id() -> str:
    return str(uuid.uuid4())


def main() -> None:
    raw_nodes = subprocess.check_output(
        [
            "docker",
            "exec",
            "agent-n8n-postgres",
            "psql",
            "-U",
            "n8n",
            "-d",
            "n8n",
            "-t",
            "-A",
            "-c",
            f"SELECT nodes FROM workflow_entity WHERE name='{WORKFLOW_NAME}';",
        ],
        text=True,
    )
    raw_conn = subprocess.check_output(
        [
            "docker",
            "exec",
            "agent-n8n-postgres",
            "psql",
            "-U",
            "n8n",
            "-d",
            "n8n",
            "-t",
            "-A",
            "-c",
            f"SELECT connections FROM workflow_entity WHERE name='{WORKFLOW_NAME}';",
        ],
        text=True,
    )

    nodes = json.loads(raw_nodes)
    connections = json.loads(raw_conn)

    nodes = [n for n in nodes if n["name"] != "Wait"]

    deploy_id = new_id()
    if_id = new_id()
    collect_id = new_id()
    error_id = new_id()

    deploy_node = {
        "parameters": {
            "method": "POST",
            "url": "http://172.18.0.1:9876/deploy",
            "authentication": "none",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "=Bearer {{ $env.DEPLOY_LISTENER_TOKEN }}",
                    }
                ]
            },
            "options": {
                "timeout": 30000,
                "response": {
                    "response": {
                        "fullResponse": True,
                    }
                },
            },
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.5,
        "position": [912, 48],
        "id": deploy_id,
        "name": "Site Deploy Tetikle",
        "executeOnce": True,
    }

    if_node = {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 3,
                },
                "conditions": [
                    {
                        "id": new_id(),
                        "leftValue": "={{ $json.statusCode }}",
                        "rightValue": 200,
                        "operator": {
                            "type": "number",
                            "operation": "equals",
                        },
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.3,
        "position": [1024, 48],
        "id": if_id,
        "name": "Deploy Basarili Mi",
    }

    collect_node = {
        "parameters": {
            "jsCode": "return $('Frontmatter Olustur').all();",
        },
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1136, 48],
        "id": collect_id,
        "name": "Telegram Icin Yazilari Topla",
    }

    error_node = {
        "parameters": {
            "chatId": "6675249884",
            "text": "=⚠️ Site deploy başarısız — Telegram linkleri gönderilmedi.\n\nHTTP durum: {{ $json.statusCode }}\n\nYanıt: {{ $json.body || $json.statusMessage || 'bilinmiyor' }}",
            "additionalFields": {},
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [1136, 200],
        "id": error_id,
        "name": "Deploy Hata Uyarisi",
        "credentials": {
            "telegramApi": {
                "id": "IPdDDgKVO9y4kgxN",
                "name": "Telegram account",
            }
        },
        "retryOnFail": True,
        "waitBetweenTries": 2000,
    }

    for n in nodes:
        if n["name"] == "Telegram Bildirimi Gonder":
            n["parameters"]["text"] = (
                "=📰 Yeni yazı yayınlandı!\n\n"
                "{{ $json.dosya_adi }}\n\n"
                "Habere gitmek için: https://bilisimpostasi.com.tr/posts/{{ $json.dosya_adi }}/"
            )
        if n["name"] == "Kuyruk Temizle Bos Icerik":
            n["executeOnce"] = True

    nodes.extend([deploy_node, if_node, collect_node, error_node])

    connections["Yaziyi Diske Yaz"] = {
        "main": [[{"node": "Site Deploy Tetikle", "type": "main", "index": 0}]]
    }
    connections["Site Deploy Tetikle"] = {
        "main": [[{"node": "Deploy Basarili Mi", "type": "main", "index": 0}]]
    }
    connections["Deploy Basarili Mi"] = {
        "main": [
            [{"node": "Telegram Icin Yazilari Topla", "type": "main", "index": 0}],
            [{"node": "Deploy Hata Uyarisi", "type": "main", "index": 0}],
        ]
    }
    connections["Telegram Icin Yazilari Topla"] = {
        "main": [[{"node": "Telegram Bildirimi Gonder", "type": "main", "index": 0}]]
    }

    if "Wait" in connections:
        del connections["Wait"]

    if "Yazilari Ayristir" in connections:
        connections["Yazilari Ayristir"] = {
            "main": [[{"node": "Yazilara Bol", "type": "main", "index": 0}]]
        }

    nodes_json = json.dumps(nodes, ensure_ascii=False).replace("'", "''")
    conn_json = json.dumps(connections, ensure_ascii=False).replace("'", "''")

    sql = f"""
UPDATE workflow_entity
SET nodes = '{nodes_json}'::json,
    connections = '{conn_json}'::json,
    "updatedAt" = NOW()
WHERE name = '{WORKFLOW_NAME}';
"""
    subprocess.run(
        ["docker", "exec", "-i", "agent-n8n-postgres", "psql", "-U", "n8n", "-d", "n8n"],
        input=sql,
        text=True,
        check=True,
    )
    print("Workflow updated")


if __name__ == "__main__":
    main()
