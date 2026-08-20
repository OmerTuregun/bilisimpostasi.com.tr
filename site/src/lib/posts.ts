import { getCollection, type CollectionEntry } from 'astro:content';
import type { Locale } from '../i18n/config';

export function postLocale(id: string): Locale {
  if (id.startsWith('en/')) return 'en';
  if (id.startsWith('tr/')) return 'tr';
  return 'tr';
}

export function postSlug(id: string): string {
  return id.replace(/^(tr|en)\//, '');
}

export async function getPosts(locale: Locale): Promise<CollectionEntry<'posts'>[]> {
  const all = await getCollection('posts');
  return all.filter((p) => postLocale(p.id) === locale);
}

export function localePrefix(locale: Locale): string {
  return locale === 'en' ? '/en' : '';
}

export function postPath(locale: Locale, slug: string): string {
  return `${localePrefix(locale)}/posts/${slug}/`;
}

export function homePath(locale: Locale, page?: number): string {
  if (locale === 'en') return page && page > 1 ? `/en/${page}/` : '/en/';
  return page && page > 1 ? `/${page}/` : '/';
}

export function categoryPath(locale: Locale, slug: string): string {
  return `${localePrefix(locale)}/kategori/${slug}/`;
}

export function categoriesIndexPath(locale: Locale): string {
  return `${localePrefix(locale)}/kategoriler/`;
}

export async function hasPostInLocale(slug: string, locale: Locale): Promise<boolean> {
  const all = await getCollection('posts');
  return all.some((p) => postSlug(p.id) === slug && postLocale(p.id) === locale);
}

export async function alternatePostPath(
  slug: string,
  from: Locale,
  to: Locale,
): Promise<string | null> {
  if (!(await hasPostInLocale(slug, to))) return null;
  return postPath(to, slug);
}

export function switchLocalePath(currentPath: string, to: Locale, alternatePost?: string | null): string {
  const isEn = currentPath === '/en' || currentPath.startsWith('/en/');
  const pathWithoutEn = isEn ? currentPath.replace(/^\/en/, '') || '/' : currentPath;

  if (pathWithoutEn.startsWith('/posts/')) {
    const slug = pathWithoutEn.replace(/^\/posts\//, '').replace(/\/$/, '');
    if (alternatePost) return postPath(to, slug);
    return homePath(to);
  }

  if (to === 'en') {
    if (pathWithoutEn === '/') return '/en/';
    return `/en${pathWithoutEn.endsWith('/') ? pathWithoutEn : `${pathWithoutEn}/`}`;
  }

  return pathWithoutEn === '/' ? '/' : pathWithoutEn;
}
