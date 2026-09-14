import { describe, expect, it } from 'vitest';
import {
  categoriesIndexPath,
  categoryPath,
  homePath,
  localePrefix,
  postLocale,
  postPath,
  postSlug,
  switchLocalePath,
} from './posts';

describe('postLocale', () => {
  it('returns en for en/ prefix', () => {
    expect(postLocale('en/some-post-20260914')).toBe('en');
  });

  it('returns tr for tr/ prefix', () => {
    expect(postLocale('tr/some-post-20260914')).toBe('tr');
  });

  it('defaults to tr when id has no locale prefix', () => {
    expect(postLocale('legacy-post-without-prefix')).toBe('tr');
  });

  it('does not treat embedded en/ as a prefix', () => {
    expect(postLocale('tr/open-source-en/foo')).toBe('tr');
  });
});

describe('postSlug', () => {
  it('strips tr/ prefix', () => {
    expect(postSlug('tr/hello-world-20260914')).toBe('hello-world-20260914');
  });

  it('strips en/ prefix', () => {
    expect(postSlug('en/hello-world-20260914')).toBe('hello-world-20260914');
  });

  it('leaves unprefixed ids unchanged', () => {
    expect(postSlug('hello-world-20260914')).toBe('hello-world-20260914');
  });
});

describe('localePrefix', () => {
  it('is empty for tr', () => {
    expect(localePrefix('tr')).toBe('');
  });

  it('is /en for en', () => {
    expect(localePrefix('en')).toBe('/en');
  });
});

describe('postPath', () => {
  it('builds TR post path with trailing slash', () => {
    expect(postPath('tr', 'foo-bar')).toBe('/posts/foo-bar/');
  });

  it('builds EN post path with /en prefix', () => {
    expect(postPath('en', 'foo-bar')).toBe('/en/posts/foo-bar/');
  });
});

describe('homePath', () => {
  it('returns / for TR home', () => {
    expect(homePath('tr')).toBe('/');
  });

  it('returns /en/ for EN home', () => {
    expect(homePath('en')).toBe('/en/');
  });

  it('paginates TR when page > 1', () => {
    expect(homePath('tr', 2)).toBe('/2/');
    expect(homePath('tr', 5)).toBe('/5/');
  });

  it('paginates EN when page > 1', () => {
    expect(homePath('en', 2)).toBe('/en/2/');
  });

  it('treats page 1 as home (no /1/)', () => {
    expect(homePath('tr', 1)).toBe('/');
    expect(homePath('en', 1)).toBe('/en/');
  });

  it('treats page 0 / undefined as home', () => {
    expect(homePath('tr', 0)).toBe('/');
    expect(homePath('tr', undefined)).toBe('/');
  });
});

describe('categoryPath', () => {
  it('builds TR category path', () => {
    expect(categoryPath('tr', 'buyuk-dil-modelleri')).toBe('/kategori/buyuk-dil-modelleri/');
  });

  it('builds EN category path', () => {
    expect(categoryPath('en', 'large-language-models')).toBe('/en/kategori/large-language-models/');
  });
});

describe('categoriesIndexPath', () => {
  it('builds locale-specific index paths', () => {
    expect(categoriesIndexPath('tr')).toBe('/kategoriler/');
    expect(categoriesIndexPath('en')).toBe('/en/kategoriler/');
  });
});

describe('switchLocalePath', () => {
  describe('home', () => {
    it('maps / to /en/ and back', () => {
      expect(switchLocalePath('/', 'en')).toBe('/en/');
      expect(switchLocalePath('/en/', 'tr')).toBe('/');
      expect(switchLocalePath('/en', 'tr')).toBe('/');
    });
  });

  describe('posts', () => {
    it('keeps post path when alternatePost is provided', () => {
      expect(switchLocalePath('/posts/some-slug/', 'en', '/en/posts/some-slug/')).toBe(
        '/en/posts/some-slug/',
      );
      expect(switchLocalePath('/en/posts/some-slug/', 'tr', '/posts/some-slug/')).toBe(
        '/posts/some-slug/',
      );
    });

    it('falls back to home when alternatePost is missing', () => {
      expect(switchLocalePath('/posts/orphan-slug/', 'en', null)).toBe('/en/');
      expect(switchLocalePath('/posts/orphan-slug/', 'en', undefined)).toBe('/en/');
      expect(switchLocalePath('/en/posts/orphan-slug/', 'tr', null)).toBe('/');
    });

    it('strips trailing slash from slug before rebuilding path', () => {
      expect(switchLocalePath('/posts/abc/', 'en', '/en/posts/abc/')).toBe('/en/posts/abc/');
    });

    it('handles post path without trailing slash', () => {
      expect(switchLocalePath('/posts/abc', 'en', '/en/posts/abc/')).toBe('/en/posts/abc/');
      expect(switchLocalePath('/en/posts/abc', 'tr', '/posts/abc/')).toBe('/posts/abc/');
    });
  });

  describe('categories with different TR/EN slugs', () => {
    it('maps buyuk-dil-modelleri ↔ large-language-models', () => {
      expect(switchLocalePath('/kategori/buyuk-dil-modelleri/', 'en')).toBe(
        '/en/kategori/large-language-models/',
      );
      expect(switchLocalePath('/en/kategori/large-language-models/', 'tr')).toBe(
        '/kategori/buyuk-dil-modelleri/',
      );
    });

    it('maps another pair (siber-guvenlik ↔ cybersecurity)', () => {
      expect(switchLocalePath('/kategori/siber-guvenlik/', 'en')).toBe(
        '/en/kategori/cybersecurity/',
      );
      expect(switchLocalePath('/en/kategori/cybersecurity/', 'tr')).toBe(
        '/kategori/siber-guvenlik/',
      );
    });

    it('accepts category path without trailing slash', () => {
      expect(switchLocalePath('/kategori/buyuk-dil-modelleri', 'en')).toBe(
        '/en/kategori/large-language-models/',
      );
    });
  });

  describe('unknown category slug', () => {
    it('falls back to categories index', () => {
      expect(switchLocalePath('/kategori/bilinmeyen-kategori/', 'en')).toBe('/en/kategoriler/');
      expect(switchLocalePath('/en/kategori/not-a-real-category/', 'tr')).toBe('/kategoriler/');
    });
  });

  describe('generic paths and trailing slash', () => {
    it('prefixes /en for TR→EN on static pages and ensures trailing slash', () => {
      expect(switchLocalePath('/hakkimizda/', 'en')).toBe('/en/hakkimizda/');
      expect(switchLocalePath('/hakkimizda', 'en')).toBe('/en/hakkimizda/');
      expect(switchLocalePath('/kategoriler/', 'en')).toBe('/en/kategoriler/');
    });

    it('strips /en for EN→TR on static pages', () => {
      expect(switchLocalePath('/en/hakkimizda/', 'tr')).toBe('/hakkimizda/');
      expect(switchLocalePath('/en/kategoriler/', 'tr')).toBe('/kategoriler/');
    });

    it('preserves path without trailing slash when switching EN→TR', () => {
      // Actual behavior: TR branch does not force a trailing slash.
      expect(switchLocalePath('/en/hakkimizda', 'tr')).toBe('/hakkimizda');
    });
  });
});
