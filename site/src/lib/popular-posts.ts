import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { Locale } from '../i18n/config';
import { DEFAULT_CATEGORY, DEFAULT_CATEGORY_EN } from './categories';
import { getPosts, postSlug, postPath } from './posts';

export type PopularPost = {
  id: string;
  title: string;
  href: string;
  views: number;
  kategori: string;
};

const CACHE_PATH = path.join(process.cwd(), '.cache', 'popular-posts.json');
const FETCH_MS = 8000;
const FETCH_LIMIT = 50;
const DEFAULT_LIMIT = 20;

let inflight = new Map<Locale, Promise<PopularPost[]>>();

function env(name: string): string {
  return (import.meta.env[name] ?? process.env[name] ?? '').toString().trim();
}

function normalize(items: unknown): PopularPost[] {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const row = item as Record<string, unknown>;
      const id = typeof row.id === 'string' ? row.id : '';
      const title = typeof row.title === 'string' ? row.title : '';
      const href = typeof row.href === 'string' ? row.href : '';
      const views = Number(row.views) || 0;
      const kategori =
        typeof row.kategori === 'string' && row.kategori.trim()
          ? row.kategori
          : DEFAULT_CATEGORY;
      if (!id || !title || !href) return null;
      return { id, title, href, views, kategori };
    })
    .filter((item): item is PopularPost => item !== null);
}

async function readCache(): Promise<PopularPost[]> {
  try {
    const raw = await readFile(CACHE_PATH, 'utf8');
    return normalize(JSON.parse(raw));
  } catch {
    return [];
  }
}

async function writeCache(items: PopularPost[]): Promise<void> {
  try {
    await mkdir(path.dirname(CACHE_PATH), { recursive: true });
    await writeFile(CACHE_PATH, JSON.stringify(items, null, 2));
  } catch {
    /* cache is best-effort */
  }
}

async function fetchJson(url: string, token: string): Promise<unknown> {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(FETCH_MS),
  });
  if (!response.ok) {
    throw new Error(`Umami ${response.status}`);
  }
  return response.json();
}

async function login(apiUrl: string): Promise<string> {
  const username = env('UMAMI_USERNAME');
  const password = env('UMAMI_PASSWORD');
  if (!username || !password) return '';
  const response = await fetch(`${apiUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    signal: AbortSignal.timeout(FETCH_MS),
  });
  if (!response.ok) throw new Error(`Umami login ${response.status}`);
  const data = (await response.json()) as { token?: string };
  return data.token ?? '';
}

function slugFromPath(raw: string): string | null {
  const pathOnly = raw.replace(/^https?:\/\/[^/]+/i, '').split('?')[0].split('#')[0];
  const match = pathOnly.match(/\/posts\/([^/]+)\/?$/);
  return match?.[1] ?? null;
}

async function fetchPopularPosts(locale: Locale): Promise<PopularPost[]> {
  try {
    const apiUrl = (env('UMAMI_API_URL') || 'http://127.0.0.1:3002').replace(/\/$/, '');
    const websiteId = env('UMAMI_WEBSITE_ID');
    if (!websiteId) return readCache();

    let token = env('UMAMI_API_TOKEN');
    if (!token) token = await login(apiUrl);
    if (!token) return readCache();

    const endAt = Date.now();
    const startAt = endAt - 7 * 24 * 60 * 60 * 1000;
    const metricsUrl =
      `${apiUrl}/api/websites/${websiteId}/metrics` +
      `?startAt=${startAt}&endAt=${endAt}&type=path&limit=${FETCH_LIMIT}`;

    let metrics: unknown;
    try {
      metrics = await fetchJson(metricsUrl, token);
    } catch {
      token = await login(apiUrl);
      if (!token) return readCache();
      metrics = await fetchJson(metricsUrl, token);
    }

    const rows = Array.isArray(metrics) ? metrics : [];
    const posts = await getPosts(locale);
    const bySlug = new Map(posts.map((post) => [postSlug(post.id), post]));
    const defaultCat = locale === 'en' ? DEFAULT_CATEGORY_EN : DEFAULT_CATEGORY;
    const seen = new Set<string>();
    const popular: PopularPost[] = [];

    for (const row of rows) {
      const rec = row && typeof row === 'object' ? (row as Record<string, unknown>) : {};
      const url = typeof rec.x === 'string' ? rec.x : '';
      const views = Number(rec.y) || 0;
      const id = slugFromPath(url);
      if (!id || seen.has(id)) continue;
      const post = bySlug.get(id);
      if (!post?.data.title?.trim()) continue;
      seen.add(id);
      popular.push({
        id,
        title: post.data.title,
        href: postPath(locale, id),
        views,
        kategori: post.data.kategori ?? defaultCat,
      });
      if (popular.length >= DEFAULT_LIMIT) break;
    }

    if (popular.length > 0) await writeCache(popular);
    return popular;
  } catch (error) {
    console.warn('[popular-posts] Umami fetch failed, using cache:', error);
    return readCache();
  }
}

export async function getPopularPosts(limit = DEFAULT_LIMIT, locale: Locale = 'tr'): Promise<PopularPost[]> {
  if (!inflight.has(locale)) inflight.set(locale, fetchPopularPosts(locale));
  const items = await inflight.get(locale)!;
  return items.slice(0, limit);
}
