#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { loadAgentConfig, loadValidAgents } from './agent-catalog-lib.mjs';

const rootDir = process.cwd();
const checkMode = process.argv.includes('--check');
const { agentConfig } = loadAgentConfig(rootDir);
const outputJsonPath = path.join(rootDir, agentConfig.catalogPath ?? 'docs/generated/agent-catalog.json');
const outputMarkdownPath = path.join(rootDir, 'docs/generated/agent-catalog.md');
const agents = loadValidAgents(rootDir).map((item) => ({
  id: item.id,
  name: item.name,
  role: item.role,
  summary: item.summary,
  surfaces: item.surfaces,
  reads: item.reads,
  writes: item.writes,
  outputs: item.outputs,
  handoff: item.handoff,
  prompt: item.prompt,
  manifestPath: item.manifestPath,
  public: item.public !== false,
}));

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[agent-catalog] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

const markdown = [
  '# Agent Catalog',
  '',
  'This generated catalog lists the repo-local agent blueprints that outsiders can inspect and reuse.',
  '',
  '## Overview',
  '',
  `- Agent count: \`${agents.length}\``,
  `- Public agents: \`${agents.filter((item) => item.public !== false).length}\``,
  '',
  '## Agents',
  '',
  '| ID | Role | Surfaces | Manifest | Writes |',
  '| --- | --- | --- | --- | --- |',
  ...(agents.length
    ? agents.map((agent) => `| \`${agent.id}\` | ${agent.role} | \`${agent.surfaces.join(', ')}\` | \`${agent.manifestPath}\` | \`${agent.writes.join(', ')}\` |`)
    : ['| none | none | none | none | none |']),
  '',
  '## How To Use',
  '',
  '- Create a new blueprint with `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`.',
  '- Refresh generated artifacts with `npm run agent:refresh` and `npm run docs:refresh`.',
  '- Search the public manifest with `npm run registry:query -- --kind agent --q "<term>"`.',
  '',
].join('\n') + '\n';

const json = `${JSON.stringify({ version: 1, agentCount: agents.length, agents }, null, 2)}\n`;

writeManaged(outputJsonPath, json);
writeManaged(outputMarkdownPath, markdown);
