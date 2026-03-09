#!/usr/bin/env node
import path from 'node:path';
import { readJson, loadRetrievalConfig, scoreRetrieval } from './context-retrieval-lib.mjs';
import { autoTelemetryEvent } from './agent-telemetry-lib.mjs';

const rootDir = process.cwd();
const { retrieval } = loadRetrievalConfig(rootDir);
const indexPath = path.join(rootDir, retrieval.indexPath ?? 'docs/generated/contextual-retrieval-index.json');
const index = readJson(indexPath);

const options = {
  query: '',
  topK: retrieval.defaultTopK ?? 5,
  surface: '',
  path: '',
  json: false,
};

for (let indexArg = 2; indexArg < process.argv.length; indexArg += 1) {
  const current = process.argv[indexArg];
  const next = process.argv[indexArg + 1];
  if (current === '--q') {
    options.query = next ?? '';
    indexArg += 1;
    continue;
  }
  if (current === '--top') {
    options.topK = Number(next ?? options.topK);
    indexArg += 1;
    continue;
  }
  if (current === '--surface') {
    options.surface = next ?? '';
    indexArg += 1;
    continue;
  }
  if (current === '--path') {
    options.path = next ?? '';
    indexArg += 1;
    continue;
  }
  if (current === '--json') {
    options.json = true;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/query-context-retrieval.mjs --q <term> [--top <n>] [--surface <id>] [--path <prefix>] [--json]');
    process.exit(0);
  }
  throw new Error(`[retrieve:query] unknown option: ${current}`);
}

if (!options.query) {
  throw new Error('[retrieve:query] --q is required');
}

const results = scoreRetrieval(index, options.query, options);
autoTelemetryEvent(rootDir, 'retrieve_query', {
  query: options.query,
  surface: options.surface,
  path: options.path,
  resultCount: results.length,
});
if (options.json) {
  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
  process.exit(0);
}

if (results.length === 0) {
  console.log('[retrieve:query] no matches');
  process.exit(0);
}

console.log('score\tpath\theadings\tpreview');
for (const item of results) {
  console.log([
    item.score.toFixed(3),
    item.path,
    (item.headings ?? []).join(' > ') || 'root',
    item.preview,
  ].join('\t'));
}
