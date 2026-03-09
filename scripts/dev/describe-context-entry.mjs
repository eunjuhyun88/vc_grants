#!/usr/bin/env node
import path from 'node:path';
import { describeManifestEntry, readJson, registryPath } from './context-registry-lib.mjs';

const rootDir = process.cwd();
const config = readJson(path.join(rootDir, 'context-kit.json'));
const manifestPath = registryPath(rootDir, config.registry?.manifestPath);
const manifest = readJson(manifestPath);
const options = {
  kind: 'all',
  id: '',
  path: '',
  title: '',
  json: false,
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--kind') {
    options.kind = process.argv[index + 1] ?? options.kind;
    index += 1;
    continue;
  }
  if (current === '--id') {
    options.id = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--path') {
    options.path = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--title') {
    options.title = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--json') {
    options.json = true;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/describe-context-entry.mjs [--kind <kind>] [--id <id>] [--path <path>] [--title <title>] [--json]');
    process.exit(0);
  }
  throw new Error(`[registry:describe] unknown option: ${current}`);
}

if (!options.id && !options.path && !options.title) {
  throw new Error('[registry:describe] provide one of --id, --path, or --title');
}

const result = describeManifestEntry(manifest, options);
if (!result) {
  console.error('[registry:describe] no matching entry');
  process.exit(1);
}

if (options.json) {
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

console.log(`kind\t${result.kind}`);
console.log(`id\t${result.id}`);
console.log(`title\t${result.title}`);
console.log(`path\t${result.path}`);
console.log(JSON.stringify(result.payload, null, 2));
