/** Cloudflare R2 public hostname (legacy URLs in frontmatter). */
export const R2_PUBLIC_BASE = 'https://pub-880c98af22074b02b5f5237e1b3a0bad.r2.dev';

/** Same-origin proxy — avoids adblock / ISP blocks on *.r2.dev */
export const MEDIA_PUBLIC_BASE = 'https://bilisimpostasi.com.tr/media';

/**
 * Rewrite cover URLs to the site `/media/` proxy so browsers do not need r2.dev.
 * Leaves already-proxied or non-R2 URLs unchanged.
 */
export function publicCoverUrl(url: string | undefined | null): string {
  if (!url) return '';
  const trimmed = url.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith(MEDIA_PUBLIC_BASE)) return trimmed;
  if (trimmed.startsWith('/media/')) return trimmed;
  if (trimmed.startsWith(R2_PUBLIC_BASE + '/')) {
    return MEDIA_PUBLIC_BASE + trimmed.slice(R2_PUBLIC_BASE.length);
  }
  if (trimmed.startsWith(R2_PUBLIC_BASE)) {
    return MEDIA_PUBLIC_BASE + trimmed.slice(R2_PUBLIC_BASE.length);
  }
  return trimmed;
}
