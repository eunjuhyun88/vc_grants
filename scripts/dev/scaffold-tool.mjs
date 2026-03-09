#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { loadToolConfig, toolDir } from './tool-catalog-lib.mjs';

const rootDir = process.cwd();
const { surfaces, toolConfig } = loadToolConfig(rootDir);
const options = {
  id: '',
  surface: toolConfig.defaultSurface,
  scope: 'local-command',
  kind: 'npm-script',
  name: '',
  summary: '',
  script: '',
  method: 'GET',
  path: '',
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--id') {
    options.id = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--surface') {
    options.surface = process.argv[index + 1] ?? options.surface;
    index += 1;
    continue;
  }
  if (current === '--scope') {
    options.scope = process.argv[index + 1] ?? options.scope;
    index += 1;
    continue;
  }
  if (current === '--kind') {
    options.kind = process.argv[index + 1] ?? options.kind;
    index += 1;
    continue;
  }
  if (current === '--name') {
    options.name = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--summary') {
    options.summary = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--script') {
    options.script = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--method') {
    options.method = process.argv[index + 1] ?? options.method;
    index += 1;
    continue;
  }
  if (current === '--path') {
    options.path = process.argv[index + 1] ?? options.path;
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/scaffold-tool.mjs --id <tool-id> [--surface <surface>] [--scope local-command|context-api|coordination] [--kind npm-script|http] [--script <npm-script>] [--method GET] [--path /route]');
    process.exit(0);
  }
  throw new Error(`[tool:new] unknown option: ${current}`);
}

if (!options.id) {
  throw new Error('[tool:new] missing required flag: --id');
}
if (!surfaces.includes(options.surface)) {
  throw new Error(`[tool:new] unknown surface: ${options.surface}`);
}
if (!/^[a-z0-9][a-z0-9-]*$/.test(options.id)) {
  throw new Error('[tool:new] id must match ^[a-z0-9][a-z0-9-]*$');
}
if (!['npm-script', 'http'].includes(options.kind)) {
  throw new Error('[tool:new] --kind must be npm-script or http');
}

const invocation = options.kind === 'http'
  ? {
      kind: 'http',
      method: options.method.toUpperCase(),
      path: options.path || '/manifest',
    }
  : {
      kind: 'npm-script',
      script: options.script || 'registry:query',
    };

const safety = options.scope === 'coordination'
  ? { sideEffects: 'writes-generated', approvalRequired: false }
  : { sideEffects: 'read-only', approvalRequired: false };

const manifest = {
  id: options.id,
  name: options.name || options.id.split('-').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' '),
  summary: options.summary || 'Describe what this tool does and when an agent should prefer it.',
  scope: options.scope,
  surfaces: [options.surface],
  reads: ['README.md', 'docs/README.md'],
  writes: options.scope === 'coordination' ? ['.agent-context/', 'docs/generated/'] : ['docs/generated/'],
  inputs: [
    { name: 'query', type: 'string', required: true, description: 'Primary lookup or operation argument.' },
  ],
  outputs: [
    { name: 'result', type: 'json', description: 'Structured output returned by the tool contract.' },
  ],
  invocation,
  safety,
  public: true,
};

const dirPath = toolDir(rootDir);
const outputPath = path.join(dirPath, `${options.id}.json`);
if (fs.existsSync(outputPath)) {
  throw new Error(`[tool:new] manifest already exists: ${path.relative(rootDir, outputPath)}`);
}

fs.mkdirSync(dirPath, { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`[tool:new] wrote ${path.relative(rootDir, outputPath)}`);
