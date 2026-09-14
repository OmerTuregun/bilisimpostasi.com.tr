/** Canonical category keys for colors / pairing across locales */
export type Locale = 'tr' | 'en';

export const defaultLocale: Locale = 'tr';
export const locales: Locale[] = ['tr', 'en'];

/**
 * Fine-grained taxonomy (14). Keys are stable; TR/EN labels+slugs are display.
 * Legacy Yapay Zeka / Teknoloji / Güvenlik map via LEGACY_* aliases for unmatched posts.
 */
export const CATEGORY_KEYS = [
  'llm',
  'cybersecurity',
  'hardware',
  'open_source',
  'software',
  'ai_agents',
  'ev_auto',
  'mobile',
  'audio',
  'space',
  'cloud',
  'iot',
  'social',
  'gaming',
] as const;

export type CategoryKey = (typeof CATEGORY_KEYS)[number];

export const CATEGORY_LABEL: Record<Locale, Record<CategoryKey, string>> = {
  tr: {
    llm: 'Büyük Dil Modelleri',
    cybersecurity: 'Siber Güvenlik',
    hardware: 'Donanım & Çipler',
    open_source: 'Açık Kaynak',
    software: 'Yazılım & Geliştirici Araçları',
    ai_agents: 'AI Ajanları & Otomasyon',
    ev_auto: 'Otonom & Elektrikli Araçlar',
    mobile: 'Mobil & Giyilebilir',
    audio: 'Ses & Kulaklık',
    space: 'Uzay & Drone',
    cloud: 'Bulut & Altyapı',
    iot: 'Akıllı Ev & IoT',
    social: 'Sosyal Medya & Platformlar',
    gaming: 'Oyun & Eğlence',
  },
  en: {
    llm: 'Large Language Models',
    cybersecurity: 'Cybersecurity',
    hardware: 'Hardware & Chips',
    open_source: 'Open Source',
    software: 'Software & Dev Tools',
    ai_agents: 'AI Agents & Automation',
    ev_auto: 'Autonomous & Electric Vehicles',
    mobile: 'Mobile & Wearables',
    audio: 'Audio & Headphones',
    space: 'Space & Drones',
    cloud: 'Cloud & Infrastructure',
    iot: 'Smart Home & IoT',
    social: 'Social Media & Platforms',
    gaming: 'Gaming & Entertainment',
  },
};

export const CATEGORY_SLUG: Record<Locale, Record<CategoryKey, string>> = {
  tr: {
    llm: 'buyuk-dil-modelleri',
    cybersecurity: 'siber-guvenlik',
    hardware: 'donanim-cipler',
    open_source: 'acik-kaynak',
    software: 'yazilim-gelistirici-araclari',
    ai_agents: 'ai-ajanlari-otomasyon',
    ev_auto: 'otonom-elektrikli-araclar',
    mobile: 'mobil-giyilebilir',
    audio: 'ses-kulaklik',
    space: 'uzay-drone',
    cloud: 'bulut-altyapi',
    iot: 'akilli-ev-iot',
    social: 'sosyal-medya-platformlar',
    gaming: 'oyun-eglence',
  },
  en: {
    llm: 'large-language-models',
    cybersecurity: 'cybersecurity',
    hardware: 'hardware-chips',
    open_source: 'open-source',
    software: 'software-dev-tools',
    ai_agents: 'ai-agents-automation',
    ev_auto: 'autonomous-electric-vehicles',
    mobile: 'mobile-wearables',
    audio: 'audio-headphones',
    space: 'space-drones',
    cloud: 'cloud-infrastructure',
    iot: 'smart-home-iot',
    social: 'social-media-platforms',
    gaming: 'gaming-entertainment',
  },
};

/** Nav / sidebar / category index order */
export const CATEGORY_ORDER: CategoryKey[] = [
  'llm',
  'ai_agents',
  'cybersecurity',
  'open_source',
  'software',
  'hardware',
  'mobile',
  'iot',
  'audio',
  'ev_auto',
  'cloud',
  'space',
  'social',
  'gaming',
];

function buildNameToKey(
  labels: Record<CategoryKey, string>,
): Record<string, CategoryKey> {
  const out: Record<string, CategoryKey> = {};
  for (const key of CATEGORY_KEYS) {
    out[labels[key]] = key;
  }
  return out;
}

export const CATEGORY_TR_TO_KEY: Record<string, CategoryKey> = {
  ...buildNameToKey(CATEGORY_LABEL.tr),
  // Legacy umbrella names (unmatched / transitional posts)
  'Yapay Zeka': 'llm',
  Teknoloji: 'hardware',
  Güvenlik: 'cybersecurity',
};

export const CATEGORY_EN_TO_KEY: Record<string, CategoryKey> = {
  ...buildNameToKey(CATEGORY_LABEL.en),
  AI: 'llm',
  Technology: 'hardware',
  Security: 'cybersecurity',
};

export function categoryKeyFromName(name: string, locale: Locale): CategoryKey {
  const map = locale === 'en' ? CATEGORY_EN_TO_KEY : CATEGORY_TR_TO_KEY;
  const raw = (name || '').trim();
  if (map[raw]) return map[raw];
  // Pipe-joined legacy values: "Yapay Zeka | Güvenlik"
  for (const part of raw.split('|').map((p) => p.trim()).filter(Boolean)) {
    if (map[part]) return map[part];
  }
  return 'hardware';
}

export function categoryLabel(key: CategoryKey, locale: Locale): string {
  return CATEGORY_LABEL[locale][key];
}

export function categorySlug(key: CategoryKey, locale: Locale): string {
  return CATEGORY_SLUG[locale][key];
}

/** n8n translation: TR frontmatter category → EN */
export const TRANSLATE_CATEGORY_TO_EN: Record<string, string> = Object.fromEntries(
  CATEGORY_KEYS.map((key) => [CATEGORY_LABEL.tr[key], CATEGORY_LABEL.en[key]]),
);
