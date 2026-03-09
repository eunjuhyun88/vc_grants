#!/usr/bin/env node
import path from 'node:path';
import { readJson, registryPath, searchManifest } from './context-registry-lib.mjs';
import { autoTelemetryEvent } from './agent-telemetry-lib.mjs';

const rootDir = process.cwd();
const config = readJson(path.join(rootDir, 'context-kit.json'));
const manifest = readJson(registryPath(rootDir, config.registry?.manifestPath));

const options = {
  query: '',
  kind: 'all',
  limit: 10,
  json: false,
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--q') {
    options.query = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--kind') {
    options.kind = process.argv[index + 1] ?? options.kind;
    index += 1;
    continue;
  }
  if (current === '--limit') {
    options.limit = Number(process.argv[index + 1] ?? options.limit);
    index += 1;
    continue;
  }
  if (current === '--json') {
    options.json = true;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/query-context-registry.mjs --q <term> [--kind surface|doc|command|retrieval|agent|tool|all] [--limit <n>] [--json]');
    process.exit(0);
  }
  throw new Error(`[registry:query] unknown option: ${current}`);
}

const results = searchManifest(manifest, options);
autoTelemetryEvent(rootDir, 'registry_query', {
  query: options.query,
  kind: options.kind,
  resultCount: results.length,
});
if (options.json) {
  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
  process.exit(0);
}

if (results.length === 0) {
  console.log('[registry:query] no matches');
  process.exit(0);
}

console.log('kind\tid\ttitle\tpath');
for (const item of results) {
  console.log([item.kind, item.id, item.title, item.path || '-'].join('\t'));
}
