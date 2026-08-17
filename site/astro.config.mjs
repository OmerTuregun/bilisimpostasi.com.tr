import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://blog.omerfarukturegun.com.tr',
  integrations: [sitemap()],
});
