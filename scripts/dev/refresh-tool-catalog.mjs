#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { loadToolConfig, loadValidTools } from './tool-catalog-lib.mjs';

const rootDir = process.cwd();
const checkMode = process.argv.includes('--check');
const { toolConfig } = loadToolConfig(rootDir);
const outputJsonPath = path.join(rootDir, toolConfig.catalogPath ?? 'docs/generated/tool-catalog.json');
const outputMarkdownPath = path.join(rootDir, 'docs/generated/tool-catalog.md');
const tools = loadValidTools(rootDir).map((item) => ({
  id: item.id,
  name: item.name,
  summary: item.summary,
  scope: item.scope,
  surfaces: item.surfaces,
  reads: item.reads ?? [],
  writes: item.writes ?? [],
  inputs: item.inputs ?? [],
  outputs: item.outputs ?? [],
  invocation: item.invocation,
  safety: item.safety,
  manifestPath: item.manifestPath,
  public: item.public !== false,
}));

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[tool-catalog] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

const markdown = [
  '# Tool Catalog',
  '',
  'This generated catalog lists repo-local tool contracts that agents can reuse without reading large free-form prompt text.',
  '',
  '## Overview',
  '',
  `- Tool count: \`${tools.length}\``,
  `- Public tools: \`${tools.filter((item) => item.public !== false).length}\``,
  '',
  '## Tools',
  '',
  '| ID | Scope | Surfaces | Safety | Invocation |',
  '| --- | --- | --- | --- | --- |',
  ...(tools.length
    ? tools.map((tool) => `| \`${tool.id}\` | ${tool.scope} | \`${tool.surfaces.join(', ')}\` | \`${tool.safety?.sideEffects ?? 'n/a'}\` | \`${tool.invocation?.kind === 'http' ? `${tool.invocation.method} ${tool.invocation.path}` : tool.invocation?.script ?? 'n/a'}\` |`)
    : ['| none | none | none | none | none |']),
  '',
  '## How To Use',
  '',
  '- Create a new tool contract with `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`.',
  '- Refresh generated artifacts with `npm run tool:refresh` and `npm run docs:refresh`.',
  '- Search the public manifest with `npm run registry:query -- --kind tool --q "<term>"`.',
  '',
].join('\n') + '\n';

const json = `${JSON.stringify({ version: 1, toolCount: tools.length, tools }, null, 2)}\n`;

writeManaged(outputJsonPath, json);
writeManaged(outputMarkdownPath, markdown);
