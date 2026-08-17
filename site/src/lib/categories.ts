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

const CATEGORY_PALETTE: Record<string, string> = {
  'Yapay Zeka': '#7c3aed',
  Teknoloji: '#2563eb',
};

export function categoryBadgeColor(name: string): string {
  return CATEGORY_PALETTE[name] ?? CATEGORY_PALETTE[DEFAULT_CATEGORY];
}

export function formatDateTime(date: Date): string {
  const dateText = new Intl.DateTimeFormat('tr-TR', {
    timeZone: 'Europe/Istanbul',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(date);
  const timeText = new Intl.DateTimeFormat('tr-TR', {
    timeZone: 'Europe/Istanbul',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(date);
  return `${dateText} · ${timeText}`;
}
