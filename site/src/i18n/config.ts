export type Locale = 'tr' | 'en';

export const defaultLocale: Locale = 'tr';
export const locales: Locale[] = ['tr', 'en'];

/** Canonical category keys for colors / pairing across locales */
export const CATEGORY_KEYS = ['ai', 'technology', 'security'] as const;
export type CategoryKey = (typeof CATEGORY_KEYS)[number];

export const CATEGORY_TR_TO_KEY: Record<string, CategoryKey> = {
  'Yapay Zeka': 'ai',
  Teknoloji: 'technology',
  Güvenlik: 'security',
};

export const CATEGORY_EN_TO_KEY: Record<string, CategoryKey> = {
  AI: 'ai',
  Technology: 'technology',
  Security: 'security',
};

export const CATEGORY_LABEL: Record<Locale, Record<CategoryKey, string>> = {
  tr: { ai: 'Yapay Zeka', technology: 'Teknoloji', security: 'Güvenlik' },
  en: { ai: 'AI', technology: 'Technology', security: 'Security' },
};

export const CATEGORY_SLUG: Record<Locale, Record<CategoryKey, string>> = {
  tr: { ai: 'yapay-zeka', technology: 'teknoloji', security: 'guvenlik' },
  en: { ai: 'ai', technology: 'technology', security: 'security' },
};

export const CATEGORY_ORDER: CategoryKey[] = ['technology', 'ai', 'security'];

export function categoryKeyFromName(name: string, locale: Locale): CategoryKey {
  const map = locale === 'en' ? CATEGORY_EN_TO_KEY : CATEGORY_TR_TO_KEY;
  return map[name] ?? 'technology';
}

export function categoryLabel(key: CategoryKey, locale: Locale): string {
  return CATEGORY_LABEL[locale][key];
}

export function categorySlug(key: CategoryKey, locale: Locale): string {
  return CATEGORY_SLUG[locale][key];
}

/** n8n translation: TR frontmatter category → EN */
export const TRANSLATE_CATEGORY_TO_EN: Record<string, string> = {
  'Yapay Zeka': 'AI',
  Teknoloji: 'Technology',
  Güvenlik: 'Security',
};
