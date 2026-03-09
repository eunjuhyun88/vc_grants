#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { buildRetrievalIndex } from './context-retrieval-lib.mjs';

const rootDir = process.cwd();
const checkMode = process.argv.includes('--check');
const index = buildRetrievalIndex(rootDir);
const indexPath = path.join(rootDir, index.retrieval.indexPath ?? 'docs/generated/contextual-retrieval-index.json');
const markdownPath = path.join(rootDir, 'docs/generated/contextual-retrieval.md');

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[contextual-retrieval] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

const topPaths = new Map();
for (const chunk of index.chunks) {
  topPaths.set(chunk.path, (topPaths.get(chunk.path) ?? 0) + 1);
}

const markdown = [
  '# Contextual Retrieval',
  '',
  'This generated artifact summarizes the query-time retrieval index for canonical docs.',
  '',
  '## Retrieval Model',
  '',
  '- Retrieval mode: deterministic contextual BM25',
  '- Chunk context: path, authority, section headings, and surface ownership are prepended before indexing',
  '- Goal: reduce full-doc scanning when the agent is uncertain what to open next',
  '',
  '## Index Stats',
  '',
  `- Source docs indexed: \`${index.sourceCount}\``,
  `- Chunks indexed: \`${index.chunkCount}\``,
  `- Chunk size (words): \`${index.retrieval.chunkWords}\``,
  `- Overlap size (words): \`${index.retrieval.overlapWords}\``,
  `- Default top-k: \`${index.retrieval.defaultTopK}\``,
  '',
  '## Top Indexed Paths',
  '',
  '| Path | Chunk Count |',
  '| --- | --- |',
  ...([...topPaths.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 15).map(([filePath, count]) => `| \`${filePath}\` | ${count} |`)),
  '',
  '## Commands',
  '',
  '- `npm run retrieve:query -- --q "<term>"`',
  '- `npm run registry:serve` then `GET /retrieve?q=<term>`',
  '',
  '## Limits',
  '',
  '- This is a lexical/contextual bootstrap index, not an embedding+rereank system.',
  '- For very large repos, the JSON index may later move to runtime-only storage.',
  '',
].join('\n') + '\n';

writeManaged(indexPath, `${JSON.stringify(index, null, 2)}\n`);
writeManaged(markdownPath, markdown);
