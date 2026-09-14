import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import type { Locale } from '../i18n/config';
import { getPosts, postPath, postSlug } from './posts';

const FEED_META: Record<
  Locale,
  { title: string; description: string; language: string; feedPath: string }
> = {
  tr: {
    title: 'Bilişim Postası — Teknoloji ve Yapay Zeka Haberleri',
    description:
      'Teknoloji ve yapay zeka dünyasındaki güncel gelişmelerin Türkçe özetleri. Yazılım, donanım, yapay zeka ve dijital dünyadan seçilmiş haberler.',
    language: 'tr',
    feedPath: '/rss.xml',
  },
  en: {
    title: 'Bilisim Postasi — Technology and AI News',
    description:
      'English summaries of technology and artificial intelligence news. Software, hardware, AI, and digital world updates.',
    language: 'en',
    feedPath: '/rss-en.xml',
  },
};

export function rssFeedPath(locale: Locale): string {
  return FEED_META[locale].feedPath;
}

export async function buildRssFeed(context: APIContext, locale: Locale) {
  const meta = FEED_META[locale];
  const posts = (await getPosts(locale))
    .filter((post) => post.data.title?.trim())
    .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());

  return rss({
    title: meta.title,
    description: meta.description,
    site: context.site!,
    items: posts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.pubDate,
      description: post.data.description,
      link: postPath(locale, postSlug(post.id)),
      categories: post.data.kategori ? [post.data.kategori] : undefined,
    })),
    customData: `<language>${meta.language}</language>`,
  });
}
