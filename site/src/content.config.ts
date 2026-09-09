import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    pubDate: z.coerce.date(),
    description: z.string(),
    kaynak: z.string().url(),
    kategori: z.string().optional().default('Donanım & Çipler'),
    tags: z.array(z.string()).optional().default([]),
    tagLabels: z
      .record(z.object({ tr: z.string(), en: z.string() }))
      .optional()
      .default({}),
    coverImage: z.string().optional(),
    gorselFotografci: z.string().optional(),
    gorselFotografciLink: z.string().optional(),
    /** Unsplash search query used for cover (debug / diagnostics) */
    gorselQuery: z.string().optional(),
    updatedDate: z.coerce.date().optional(),
  }),
});

export const collections = { posts };
