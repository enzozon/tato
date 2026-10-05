import sharp from 'sharp';
import { mkdir, readFile } from 'node:fs/promises';
await mkdir('public/icons', { recursive: true });
const svg = await readFile('../../packages/mascot/icon.svg');
for (const size of [180,192,512]) {
  await sharp(svg).resize(size,size).png().toFile(`public/icons/${size}.png`);
}
