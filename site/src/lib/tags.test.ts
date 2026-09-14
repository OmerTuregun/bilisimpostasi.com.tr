import { describe, expect, it } from 'vitest';
import {
  mergeTagLabels,
  normalizeTags,
  tagLabel,
  tagPath,
  buildTagRegistry,
  collectTagSlugs,
  postsWithTag,
  type TagLabels,
} from './tags';

describe('normalizeTags', () => {
  it('returns empty array for undefined or empty', () => {
    expect(normalizeTags(undefined)).toEqual([]);
    expect(normalizeTags([])).toEqual([]);
  });

  it('trims, lowercases, dedupes, and drops blanks', () => {
    expect(normalizeTags(['  AI ', 'ai', 'Rust', '', '  '])).toEqual(['ai', 'rust']);
  });
});

describe('mergeTagLabels', () => {
  it('merges sources; later overrides earlier for same slug', () => {
    const a: TagLabels = { llama: { tr: 'Llama', en: 'Llama' } };
    const b: TagLabels = { llama: { tr: 'Llama 3', en: 'Llama 3' }, gpt: { tr: 'GPT', en: 'GPT' } };
    expect(mergeTagLabels(a, b)).toEqual({
      llama: { tr: 'Llama 3', en: 'Llama 3' },
      gpt: { tr: 'GPT', en: 'GPT' },
    });
  });

  it('skips undefined sources and incomplete label pairs', () => {
    expect(
      mergeTagLabels(undefined, {
        ok: { tr: 'Tamam', en: 'OK' },
        bad: { tr: '', en: 'X' } as TagLabels[string],
      }),
    ).toEqual({ ok: { tr: 'Tamam', en: 'OK' } });
  });

  it('normalizes slug keys to lowercase trimmed', () => {
    expect(mergeTagLabels({ '  Foo ': { tr: 'Foo', en: 'Foo' } })).toEqual({
      foo: { tr: 'Foo', en: 'Foo' },
    });
  });
});

describe('tagLabel', () => {
  const registry: TagLabels = {
    guvenlik: { tr: 'Güvenlik', en: 'Security' },
  };

  it('prefers postLabels over registry', () => {
    expect(
      tagLabel('guvenlik', 'tr', registry, {
        guvenlik: { tr: 'Özel', en: 'Custom' },
      }),
    ).toBe('Özel');
  });

  it('uses registry when postLabels missing', () => {
    expect(tagLabel('guvenlik', 'en', registry)).toBe('Security');
  });

  it('falls back to title-cased slug parts', () => {
    expect(tagLabel('large-language-models', 'tr')).toBe('Large Language Models');
  });
});

describe('tagPath', () => {
  it('builds TR and EN tag paths', () => {
    expect(tagPath('tr', 'rust')).toBe('/etiket/rust/');
    expect(tagPath('en', 'rust')).toBe('/en/etiket/rust/');
  });
});

describe('buildTagRegistry / collectTagSlugs / postsWithTag', () => {
  const posts = [
    {
      id: 'tr/a',
      data: {
        pubDate: new Date('2026-09-10T12:00:00Z'),
        tags: ['ai', 'rust'],
        tagLabels: { ai: { tr: 'YZ', en: 'AI' } },
      },
    },
    {
      id: 'tr/b',
      data: {
        pubDate: new Date('2026-09-12T12:00:00Z'),
        tags: ['AI', 'linux'],
        tagLabels: { ai: { tr: 'Yapay Zeka', en: 'Artificial Intelligence' } },
      },
    },
  ] as unknown as import('astro:content').CollectionEntry<'posts'>[];

  it('buildTagRegistry: newer posts win for label conflicts', () => {
    expect(buildTagRegistry(posts).ai).toEqual({
      tr: 'Yapay Zeka',
      en: 'Artificial Intelligence',
    });
  });

  it('collectTagSlugs: unique sorted slugs', () => {
    expect(collectTagSlugs(posts)).toEqual(['ai', 'linux', 'rust']);
  });

  it('postsWithTag: filters and sorts by pubDate desc', () => {
    const withAi = postsWithTag(posts, 'ai');
    expect(withAi.map((p) => p.id)).toEqual(['tr/b', 'tr/a']);
    expect(postsWithTag(posts, 'linux')).toHaveLength(1);
    expect(postsWithTag(posts, 'missing')).toHaveLength(0);
  });
});
