import type { CollectionEntry } from 'astro:content';
import type { Locale } from '../i18n/config';
import { localePrefix } from './posts';

export type TagLabelPair = { tr: string; en: string };
export type TagLabels = Record<string, TagLabelPair>;

function slugFallbackLabel(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

/** Merge tag label maps; later sources override earlier ones for the same slug. */
export function mergeTagLabels(...sources: (TagLabels | undefined)[]): TagLabels {
  const out: TagLabels = {};
  for (const src of sources) {
    if (!src) continue;
    for (const [slug, labels] of Object.entries(src)) {
      const key = slug.trim().toLowerCase();
      if (!key || !labels?.tr || !labels?.en) continue;
      out[key] = { tr: labels.tr.trim(), en: labels.en.trim() };
    }
  }
  return out;
}

/** Build a site-wide tag label registry from posts (newer posts win). */
export function buildTagRegistry(posts: CollectionEntry<'posts'>[]): TagLabels {
  const sorted = [...posts].sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
  const registry: TagLabels = {};
  for (const post of sorted) {
    Object.assign(registry, mergeTagLabels(post.data.tagLabels));
  }
  return registry;
}

/** Display label for a tag slug in the given locale. */
export function tagLabel(
  slug: string,
  locale: Locale = 'tr',
  registry?: TagLabels,
  postLabels?: TagLabels,
): string {
  const key = slug.trim().toLowerCase();
  const labels = postLabels?.[key] ?? registry?.[key];
  if (labels) return labels[locale];
  return slugFallbackLabel(key);
}

export function tagPath(locale: Locale, slug: string): string {
  return `${localePrefix(locale)}/etiket/${slug}/`;
}

export function normalizeTags(tags: string[] | undefined): string[] {
  if (!tags?.length) return [];
  return [...new Set(tags.map((t) => t.trim().toLowerCase()).filter(Boolean))];
}

export function collectTagSlugs(posts: CollectionEntry<'posts'>[]): string[] {
  const slugs = new Set<string>();
  for (const post of posts) {
    for (const tag of normalizeTags(post.data.tags)) {
      slugs.add(tag);
    }
  }
  return [...slugs].sort((a, b) => a.localeCompare(b, 'tr'));
}

export function postsWithTag(
  posts: CollectionEntry<'posts'>[],
  tag: string,
): CollectionEntry<'posts'>[] {
  const needle = tag.toLowerCase();
  return posts
    .filter((post) => normalizeTags(post.data.tags).includes(needle))
    .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}
