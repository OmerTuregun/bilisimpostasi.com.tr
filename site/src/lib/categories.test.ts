import { describe, expect, it } from 'vitest';
import {
  categoryBadgeColor,
  DEFAULT_CATEGORY,
  DEFAULT_CATEGORY_EN,
  formatDateTime,
  getCategoryDisplayName,
  getCategoryKey,
  getCategoryUrlSlug,
  navCategoriesFromPosts,
  slugifyCategory,
} from './categories';

describe('slugifyCategory', () => {
  it('transliterates Turkish characters and slugifies', () => {
    expect(slugifyCategory('Büyük Dil Modelleri')).toBe('buyuk-dil-modelleri');
    expect(slugifyCategory('Donanım & Çipler')).toBe('donanim-cipler');
    expect(slugifyCategory('  Açık Kaynak  ')).toBe('acik-kaynak');
  });

  it('collapses non-alphanumerics and trims hyphens', () => {
    expect(slugifyCategory('Foo---Bar!!!')).toBe('foo-bar');
  });
});

describe('getCategoryKey', () => {
  it('maps known TR/EN labels to keys', () => {
    expect(getCategoryKey('Büyük Dil Modelleri', 'tr')).toBe('llm');
    expect(getCategoryKey('Large Language Models', 'en')).toBe('llm');
    expect(getCategoryKey('Siber Güvenlik', 'tr')).toBe('cybersecurity');
  });

  it('maps legacy umbrella names', () => {
    expect(getCategoryKey('Yapay Zeka', 'tr')).toBe('llm');
    expect(getCategoryKey('Teknoloji', 'tr')).toBe('hardware');
    expect(getCategoryKey('AI', 'en')).toBe('llm');
  });

  it('handles pipe-joined legacy values', () => {
    expect(getCategoryKey('Yapay Zeka | Güvenlik', 'tr')).toBe('llm');
  });

  it('falls back to hardware for unknown names', () => {
    expect(getCategoryKey('Bilinmeyen Kategori', 'tr')).toBe('hardware');
    expect(getCategoryKey('', 'en')).toBe('hardware');
  });
});

describe('getCategoryDisplayName / getCategoryUrlSlug', () => {
  it('returns canonical display name for the same-locale label', () => {
    expect(getCategoryDisplayName('Büyük Dil Modelleri', 'tr')).toBe('Büyük Dil Modelleri');
    expect(getCategoryDisplayName('Large Language Models', 'en')).toBe('Large Language Models');
  });

  it('returns locale-specific URL slug from a same-locale name', () => {
    expect(getCategoryUrlSlug('Büyük Dil Modelleri', 'tr')).toBe('buyuk-dil-modelleri');
    expect(getCategoryUrlSlug('Large Language Models', 'en')).toBe('large-language-models');
    expect(getCategoryUrlSlug(DEFAULT_CATEGORY, 'tr')).toBe('donanim-cipler');
    expect(getCategoryUrlSlug(DEFAULT_CATEGORY_EN, 'en')).toBe('hardware-chips');
  });
});

describe('categoryBadgeColor', () => {
  it('returns palette color for known categories', () => {
    expect(categoryBadgeColor('Büyük Dil Modelleri', 'tr')).toBe('#5b21b6');
    expect(categoryBadgeColor('Siber Güvenlik', 'tr')).toBe('#b45309');
  });

  it('falls back to hardware color for unknown', () => {
    expect(categoryBadgeColor('???', 'tr')).toBe('#334155');
  });
});

describe('formatDateTime', () => {
  it('formats a fixed instant in Europe/Istanbul for TR and EN', () => {
    const date = new Date('2026-09-14T12:00:00.000Z'); // 15:00 Istanbul (UTC+3)
    const tr = formatDateTime(date, 'tr');
    const en = formatDateTime(date, 'en');
    expect(tr).toMatch(/14/);
    expect(tr).toMatch(/2026/);
    expect(tr).toMatch(/15:00/);
    expect(tr).toContain('·');
    expect(en).toMatch(/14/);
    expect(en).toMatch(/2026/);
    expect(en).toMatch(/15:00/);
  });
});

describe('navCategoriesFromPosts', () => {
  it('returns unique categories in CATEGORY_ORDER, only those present', () => {
    const posts = [
      { data: { kategori: 'Siber Güvenlik' } },
      { data: { kategori: 'Büyük Dil Modelleri' } },
      { data: { kategori: 'Siber Güvenlik' } },
      { data: {} },
    ];
    const nav = navCategoriesFromPosts(posts, 'tr');
    expect(nav.map((c) => c.key)).toEqual(['llm', 'cybersecurity', 'hardware']);
    expect(nav[0]).toMatchObject({
      key: 'llm',
      name: 'Büyük Dil Modelleri',
      slug: 'buyuk-dil-modelleri',
    });
  });
});
