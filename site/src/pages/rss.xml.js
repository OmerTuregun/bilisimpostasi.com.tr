import rss from '@astrojs/rss';
import { getPosts, postPath, postSlug } from '../lib/posts';
import { t } from '../i18n/ui';

export async function GET(context) {
  const locale = 'tr';
  const strings = t(locale);
  const posts = (await getPosts(locale))
    .filter((post) => post.data.title?.trim())
    .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());

  return rss({
    title: strings.homeTitle,
    description: strings.homeDesc,
    site: context.site,
    items: posts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.pubDate,
      description: post.data.description,
      link: postPath(locale, postSlug(post.id)),
    })),
    customData: '<language>tr</language>',
  });
}
