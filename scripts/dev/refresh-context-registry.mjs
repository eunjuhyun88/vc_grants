#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { readJson } from './context-registry-lib.mjs';
import { loadValidAgents } from './agent-catalog-lib.mjs';
import { loadValidTools } from './tool-catalog-lib.mjs';

const rootDir = process.cwd();
const config = readJson(path.join(rootDir, 'context-kit.json'));
const checkMode = process.argv.includes('--check');
const generatedDir = path.join(rootDir, 'docs/generated');
const markdownPath = path.join(generatedDir, 'context-registry.md');
const jsonPath = path.join(rootDir, config.registry?.manifestPath ?? 'docs/generated/context-registry.json');

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function relative(filePath) {
  return path.relative(rootDir, filePath).split(path.sep).join('/');
}

function loadPackageScripts() {
  const pkg = readJson(path.join(rootDir, 'package.json'));
  return Object.entries(pkg.scripts ?? {})
    .filter(([name]) => /^(docs|ctx|coord|agent|tool|harness|registry|retrieve|eval|sandbox|safe):/.test(name) || ['docs:check', 'gate:context'].includes(name))
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, script]) => ({
      name,
      script,
      category: name.split(':')[0],
    }));
}

function canonicalDocs() {
  const coreDocs = [
    ['README.md', 'root-router', 'canonical'],
    ['AGENTS.md', 'agent-rules', 'canonical'],
    ['ARCHITECTURE.md', 'architecture-map', 'canonical'],
    ['docs/README.md', 'docs-router', 'canonical'],
    ['docs/SYSTEM_INTENT.md', 'system-intent', 'canonical'],
    ['docs/CONTEXT_ENGINEERING.md', 'context-engineering', 'canonical'],
    ['docs/CONTEXT_EVALUATION.md', 'context-evaluation', 'canonical'],
    ['docs/CONTEXT_PLATFORM.md', 'context-platform', 'canonical'],
    ['docs/AGENT_FACTORY.md', 'agent-factory', 'canonical'],
    ['docs/TOOL_DESIGN.md', 'tool-design', 'canonical'],
    ['docs/AGENT_OBSERVABILITY.md', 'agent-observability', 'canonical'],
    ['docs/MULTI_AGENT_COORDINATION.md', 'coordination', 'canonical'],
    ['docs/SANDBOX_POLICY.md', 'sandbox-policy', 'canonical'],
    ['docs/DESIGN.md', 'design-authority', 'canonical'],
    ['docs/ENGINEERING.md', 'engineering-authority', 'canonical'],
    ['docs/PLANS.md', 'planning-authority', 'canonical'],
    ['docs/PRODUCT_SENSE.md', 'product-heuristics', 'canonical'],
    ['docs/QUALITY_SCORE.md', 'quality-score', 'canonical'],
    ['docs/RELIABILITY.md', 'reliability', 'canonical'],
    ['docs/SECURITY.md', 'security', 'canonical'],
    ['docs/HARNESS.md', 'harness', 'canonical'],
  ];

  const surfaceDocs = (config.surfaces ?? [])
    .filter((surface) => surface.spec)
    .map((surface) => [surface.spec, `surface-${surface.id}`, 'surface-canonical']);

  return [...coreDocs, ...surfaceDocs]
    .filter(([filePath]) => fs.existsSync(path.join(rootDir, filePath)))
    .map(([filePath, role, authority]) => ({
      path: filePath,
      role,
      authority,
    }));
}

function buildManifest() {
  const registry = config.registry ?? {};
  const retrievalIndex = readJson(path.join(rootDir, config.retrieval?.indexPath ?? 'docs/generated/contextual-retrieval-index.json'));
  const agents = loadValidAgents(rootDir).map((agent) => ({
    id: agent.id,
    name: agent.name,
    role: agent.role,
    summary: agent.summary,
    surfaces: agent.surfaces,
    manifestPath: agent.manifestPath,
    outputs: agent.outputs,
    handoff: agent.handoff,
    public: agent.public !== false,
  }));
  const tools = loadValidTools(rootDir).map((tool) => ({
    id: tool.id,
    name: tool.name,
    summary: tool.summary,
    scope: tool.scope,
    surfaces: tool.surfaces,
    reads: tool.reads,
    writes: tool.writes,
    inputs: tool.inputs,
    outputs: tool.outputs,
    invocation: tool.invocation,
    safety: tool.safety,
    manifestPath: tool.manifestPath,
    public: tool.public !== false,
  }));
  return {
    version: 1,
    project: config.project ?? {},
    discovery: config.discovery ?? {},
    registry: {
      enabled: registry.enabled ?? true,
      manifestPath: registry.manifestPath ?? 'docs/generated/context-registry.json',
      publicBaseUrl: registry.publicBaseUrl ?? '',
      publishTags: registry.publishTags ?? [],
      searchKinds: registry.searchKinds ?? ['surface', 'doc', 'command', 'retrieval', 'agent', 'tool'],
    },
    capabilities: {
      routing: true,
      generatedMaps: true,
      runtimeMemory: true,
      coordination: true,
      benchmark: true,
      registryQuery: true,
      contextualRetrieval: true,
      agentBlueprints: true,
      toolContracts: true,
      agentTelemetry: true,
      taskAB: true,
      sandboxPolicy: true,
    },
    surfaces: (config.surfaces ?? []).map((surface) => ({
      id: surface.id,
      label: surface.label ?? surface.id,
      summary: surface.summary ?? '',
      spec: surface.spec ?? '',
      routes: surface.routes ?? [],
      stores: surface.stores ?? [],
      apis: surface.apis ?? [],
    })),
    docs: canonicalDocs(),
    commands: loadPackageScripts(),
    agents,
    tools,
    telemetry: {
      enabled: config.telemetry?.enabled ?? true,
      reportPath: config.telemetry?.reportPath ?? 'docs/generated/agent-usage-report.json',
    },
    retrieval: {
      enabled: config.retrieval?.enabled ?? true,
      indexPath: config.retrieval?.indexPath ?? 'docs/generated/contextual-retrieval-index.json',
      chunkCount: retrievalIndex.chunkCount ?? 0,
      sourceCount: retrievalIndex.sourceCount ?? 0,
      sources: (retrievalIndex.chunks ?? []).slice(0, 200).map((item) => ({
        path: item.path,
        role: item.role,
        authority: item.authority,
      })).filter((item, index, array) => array.findIndex((cursor) => cursor.path === item.path) === index),
    },
  };
}

function manifestMarkdown(manifest) {
  const surfaceRows = (manifest.surfaces ?? []).map((surface) => `| \`${surface.id}\` | ${surface.label} | \`${surface.spec || '-'}\` | ${(surface.routes ?? []).join(', ') || '-'} |`);
  const docRows = (manifest.docs ?? []).map((doc) => `| \`${doc.path}\` | ${doc.role} | ${doc.authority} |`);
  const commandRows = (manifest.commands ?? []).map((command) => `| \`${command.name}\` | ${command.category} | \`${command.script}\` |`);
  const agentRows = (manifest.agents ?? []).map((agent) => `| \`${agent.id}\` | ${agent.role} | \`${(agent.surfaces ?? []).join(', ')}\` | \`${agent.manifestPath}\` |`);
  const toolRows = (manifest.tools ?? []).map((tool) => `| \`${tool.id}\` | ${tool.scope} | \`${(tool.surfaces ?? []).join(', ')}\` | \`${tool.manifestPath}\` |`);
  const publicBaseUrl = manifest.registry?.publicBaseUrl ?? '';

  return [
    '# Context Registry',
    '',
    'This generated manifest is the portable index for open-source discovery, local API serving, and agent-side search.',
    '',
    '## Registry Overview',
    '',
    `- Registry enabled: \`${manifest.registry?.enabled ? 'yes' : 'no'}\``,
    `- Public base URL: \`${publicBaseUrl || 'not configured'}\``,
    `- Search kinds: \`${(manifest.registry?.searchKinds ?? []).join(', ') || 'none'}\``,
    `- Publish tags: \`${(manifest.registry?.publishTags ?? []).join(', ') || 'none'}\``,
    '',
    '## Surfaces',
    '',
    '| Surface | Label | Spec | Routes |',
    '| --- | --- | --- | --- |',
    ...(surfaceRows.length ? surfaceRows : ['| none | none | none | none |']),
    '',
    '## Canonical Docs',
    '',
    '| Path | Role | Authority |',
    '| --- | --- | --- |',
    ...(docRows.length ? docRows : ['| none | none | none |']),
    '',
    '## Commands',
    '',
    '| Command | Category | Script |',
    '| --- | --- | --- |',
    ...(commandRows.length ? commandRows : ['| none | none | none |']),
    '',
    '## Agents',
    '',
    '| Agent | Role | Surfaces | Manifest |',
    '| --- | --- | --- | --- |',
    ...(agentRows.length ? agentRows : ['| none | none | none | none |']),
    '',
    '## Tools',
    '',
    '| Tool | Scope | Surfaces | Manifest |',
    '| --- | --- | --- | --- |',
    ...(toolRows.length ? toolRows : ['| none | none | none | none |']),
    '',
    '## Retrieval',
    '',
    `- Retrieval enabled: \`${manifest.retrieval?.enabled ? 'yes' : 'no'}\``,
    `- Indexed sources: \`${manifest.retrieval?.sourceCount ?? 0}\``,
    `- Indexed chunks: \`${manifest.retrieval?.chunkCount ?? 0}\``,
    '',
    '## Telemetry',
    '',
    `- Telemetry enabled: \`${manifest.telemetry?.enabled ? 'yes' : 'no'}\``,
    `- Usage report: \`${manifest.telemetry?.reportPath ?? 'not configured'}\``,
    '',
    '## How To Use',
    '',
    '- Query locally with `npm run registry:query -- --q "<term>"`.',
    '- Search just agents with `npm run registry:query -- --kind agent --q "<term>"`.',
    '- Search reusable tools with `npm run registry:query -- --kind tool --q "<term>"`.',
    '- Inspect one contract with `npm run registry:describe -- --kind "<kind>" --id "<id>"`.',
    '- Record measured work with `npm run agent:start`, `npm run agent:event`, `npm run agent:finish`, and `npm run agent:report`.',
    '- Query retrieval chunks with `npm run retrieve:query -- --q "<term>"`.',
    '- Scaffold a new blueprint with `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`.',
    '- Scaffold a new tool contract with `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`.',
    '- Serve locally with `npm run registry:serve` to expose `/manifest`, `/agents`, `/tools`, and `/search`.',
    '- Publish the JSON manifest if you want external agents or indexes to discover this repo.',
    '',
  ].join('\n') + '\n';
}

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[context-registry] stale generated file: ${relative(filePath)}`);
    }
    return;
  }
  fs.writeFileSync(filePath, content);
}

ensureDir(generatedDir);
ensureDir(path.dirname(jsonPath));
const manifest = buildManifest();
const markdown = manifestMarkdown(manifest);
const json = `${JSON.stringify(manifest, null, 2)}\n`;
writeManaged(markdownPath, markdown);
writeManaged(jsonPath, json);
