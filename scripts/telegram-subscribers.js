#!/usr/bin/env node
/**
 * Update telegram-subscribers.jsonl stored under /home/node/data.
 * Intended to be called from n8n Execute Command with a flock lock held.
 */

const fs = require('fs');
const path = require('path');

const [action, chatIdRaw] = process.argv.slice(2);
if (!action || !chatIdRaw) {
  console.error('Usage: telegram-subscribers.js <subscribe|unsubscribe> <chat_id>');
  process.exit(2);
}

const chatId = Number(chatIdRaw);
if (!Number.isFinite(chatId)) {
  console.error('Invalid chat_id:', chatIdRaw);
  process.exit(2);
}

const DATA_DIR = '/home/node/data';
const FILE = path.join(DATA_DIR, 'telegram-subscribers.jsonl');

function readAll() {
  try {
    const raw = fs.readFileSync(FILE, 'utf8');
    return raw
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => {
        try {
          return JSON.parse(l);
        } catch {
          return null;
        }
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

function writeAll(items) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const out = items.map((x) => JSON.stringify(x)).join('\n') + (items.length ? '\n' : '');
  const tmp = `${FILE}.tmp`;
  fs.writeFileSync(tmp, out, 'utf8');
  fs.renameSync(tmp, FILE);
}

const items = readAll();
let next = [];

if (action === 'subscribe') {
  next = items.filter((x) => Number(x.chat_id) !== chatId);
  next.push({ chat_id: chatId, eklenme_zamani: new Date().toISOString() });
  next.sort((a, b) => Number(a.chat_id) - Number(b.chat_id));
} else if (action === 'unsubscribe') {
  next = items.filter((x) => Number(x.chat_id) !== chatId);
} else {
  console.error('Unknown action:', action);
  process.exit(2);
}

writeAll(next);
console.log('OK', action, chatId, 'count', next.length);

