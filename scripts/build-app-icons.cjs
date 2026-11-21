/* Regenerate launcher icons from the project's vector identity. Requires sharp. */
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');

(async () => {
  const directory = path.resolve(__dirname, '../core/static/core/brand');
  const source = path.join(directory, 'icon.svg');
  const variants = [
    ['icon-192.png', 192], ['icon-512.png', 512],
    ['icon-maskable-512.png', 512], ['apple-touch-icon.png', 180], ['favicon-32.png', 32],
  ];
  for (const [name, size] of variants) {
    await sharp(source).resize(size, size).png().toFile(path.join(directory, name));
  }
  console.log(`Generated ${variants.length} Residencia Segura icons.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
