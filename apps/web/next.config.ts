import type { NextConfig } from 'next';
import path from 'node:path';

const config: NextConfig = {
  output: 'export',
  turbopack: { root: path.resolve(import.meta.dirname, '../..') },
  trailingSlash: true,
  poweredByHeader: false,
  images: { unoptimized: true },
};
export default config;
