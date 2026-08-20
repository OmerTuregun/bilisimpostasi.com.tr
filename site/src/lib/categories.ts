import {
  type CategoryKey,
  type Locale,
  CATEGORY_LABEL,
  CATEGORY_SLUG,
  categoryKeyFromName,
  categoryLabel,
  categorySlug,
} from '../i18n/config';

const TR_MAP: Record<string, string> = {
  ç: 'c', Ç: 'c', ğ: 'g', Ğ: 'g', ı: 'i', İ: 'i',
  ö: 'o', Ö: 'o', ş: 's', Ş: 's', ü: 'u', Ü: 'u',
};

export function slugifyCategory(name: string): string {
  let value = name.trim();
  for (const [from, to] of Object.entries(TR_MAP)) {
    value = value.split(from).join(to);
  }
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export const DEFAULT_CATEGORY = 'Teknoloji';
export const DEFAULT_CATEGORY_EN = 'Technology';

const CATEGORY_PALETTE: Record<CategoryKey, string> = {
  ai: '#7c3aed',
  technology: '#2563eb',
  security: '#d97706',
};

export function getCategoryKey(name: string, locale: Locale): CategoryKey {
  return categoryKeyFromName(name, locale);
}

export function getCategoryDisplayName(name: string, locale: Locale): string {
  const key = getCategoryKey(name, locale);
  return categoryLabel(key, locale);
}

export function getCategoryUrlSlug(name: string, locale: Locale): string {
  const key = getCategoryKey(name, locale);
  return categorySlug(key, locale);
}

export function categoryBadgeColor(name: string, locale: Locale = 'tr'): string {
  const key = getCategoryKey(name, locale);
  return CATEGORY_PALETTE[key] ?? CATEGORY_PALETTE.technology;
}

export function formatDateTime(date: Date, locale: Locale = 'tr'): string {
  const intlLocale = locale === 'en' ? 'en-GB' : 'tr-TR';
  const dateText = new Intl.DateTimeFormat(intlLocale, {
    timeZone: 'Europe/Istanbul',
    year: 'numeric',
    month: locale === 'en' ? 'short' : 'long',
    day: 'numeric',
  }).format(date);
  const timeText = new Intl.DateTimeFormat(intlLocale, {
    timeZone: 'Europe/Istanbul',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(date);
  return `${dateText} · ${timeText}`;
}

export function navCategoriesFromPosts(
  posts: { data: { kategori?: string } }[],
  locale: Locale,
): { name: string; slug: string; key: CategoryKey }[] {
  const keys = new Set<CategoryKey>();
  for (const post of posts) {
    keys.add(getCategoryKey(post.data.kategori ?? DEFAULT_CATEGORY, locale));
  }
  const order: CategoryKey[] = ['technology', 'ai', 'security'];
  return order
    .filter((k) => keys.has(k))
    .map((key) => ({
      key,
      name: CATEGORY_LABEL[locale][key],
      slug: CATEGORY_SLUG[locale][key],
    }));
}
