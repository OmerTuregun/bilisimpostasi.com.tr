import { buildRssFeed } from '../lib/rss';

export async function GET(context) {
  return buildRssFeed(context, 'tr');
}
