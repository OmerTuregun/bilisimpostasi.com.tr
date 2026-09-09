import {
  type CategoryKey,
  type Locale,
  CATEGORY_LABEL,
  CATEGORY_ORDER,
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

export const DEFAULT_CATEGORY = 'Donanım & Çipler';
export const DEFAULT_CATEGORY_EN = 'Hardware & Chips';

const CATEGORY_PALETTE: Record<CategoryKey, string> = {
  llm: '#5b21b6',
  ai_agents: '#7c3aed',
  cybersecurity: '#b45309',
  open_source: '#0f766e',
  software: '#1d4ed8',
  hardware: '#334155',
  mobile: '#0369a1',
  iot: '#15803d',
  audio: '#a21caf',
  ev_auto: '#c2410c',
  cloud: '#075985',
  space: '#1e3a8a',
  social: '#be123c',
  gaming: '#4f46e5',
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
  return CATEGORY_PALETTE[key] ?? CATEGORY_PALETTE.hardware;
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
  return CATEGORY_ORDER.filter((k) => keys.has(k)).map((key) => ({
    key,
    name: CATEGORY_LABEL[locale][key],
    slug: CATEGORY_SLUG[locale][key],
  }));
}
