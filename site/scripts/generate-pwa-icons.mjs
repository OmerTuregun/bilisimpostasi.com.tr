#!/usr/bin/env node
/**
 * PWA icons from the site logo (public/favicon-512.png — BP monogram, same as favicon/header).
 * Regenerate after logo changes: npm run icons
 */
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const sourceLogo = join(root, 'public/favicon-512.png');
const outDir = join(root, 'public/icons');

/** Maskable safe zone: logo fits ~72% of canvas (Android circular mask). */
const MASKABLE_SCALE = 0.72;
const LOGO_BG = { r: 0, g: 0, b: 0, alpha: 1 };

mkdirSync(outDir, { recursive: true });

async function writeRegular(size) {
  await sharp(sourceLogo)
    .resize(size, size, { fit: 'cover' })
    .png()
    .toFile(join(outDir, `icon-${size}.png`));
}

async function writeMaskable(size) {
  const logoSize = Math.round(size * MASKABLE_SCALE);
  const offset = Math.round((size - logoSize) / 2);
  const logo = await sharp(sourceLogo)
    .resize(logoSize, logoSize, { fit: 'contain', background: LOGO_BG })
    .png()
    .toBuffer();

  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: LOGO_BG,
    },
  })
    .composite([{ input: logo, left: offset, top: offset }])
    .png()
    .toFile(join(outDir, `icon-${size}-maskable.png`));
}

for (const size of [192, 512]) {
  await writeRegular(size);
  await writeMaskable(size);
}

console.log(`PWA icons generated from ${sourceLogo} -> ${outDir}/`);
