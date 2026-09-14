import { describe, expect, it } from 'vitest';
import { rssFeedPath } from './rss';

describe('rssFeedPath', () => {
  it('returns TR and EN feed paths', () => {
    expect(rssFeedPath('tr')).toBe('/rss.xml');
    expect(rssFeedPath('en')).toBe('/rss-en.xml');
  });
});
