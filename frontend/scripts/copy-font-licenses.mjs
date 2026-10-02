import { copyFile, mkdir } from 'node:fs/promises'
const destination = new URL('../dist/assets/licenses/', import.meta.url)
await mkdir(destination, { recursive: true })
for (const [pkg, name] of [
  ['@fontsource-variable/geist', 'geist'],
  ['@fontsource-variable/geist-mono', 'geist-mono'],
  ['@fontsource/instrument-serif', 'instrument-serif'],
]) await copyFile(new URL(`../node_modules/${pkg}/LICENSE`, import.meta.url), new URL(`${name}.txt`, destination))
