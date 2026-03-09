#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const docsDir = path.join(rootDir, 'docs');
const generatedDir = path.join(docsDir, 'generated');
const configPath = path.join(rootDir, 'context-kit.json');
const checkMode = process.argv.includes('--check');
const generatedSelfRefs = new Set([
  'docs/generated/docs-catalog.md',
  'docs/generated/legacy-doc-audit.md',
  'docs/generated/context-contract-report.md',
  'docs/generated/context-efficiency-report.md',
  'docs/generated/contextual-retrieval.md',
  'docs/generated/agent-catalog.md',
  'docs/generated/tool-catalog.md',
  'docs/generated/agent-usage-report.md',
  'docs/generated/context-registry.md',
  'docs/generated/context-ab-report.md',
  'docs/generated/sandbox-policy-report.md',
  'docs/generated/context-value-demo.md',
  'docs/generated/claude-compatibility-bootstrap.md',
]);
const virtualExistingRefs = new Set([
  'docs/generated/route-map.md',
  'docs/generated/store-authority-map.md',
  'docs/generated/api-group-map.md',
  'docs/generated/docs-catalog.md',
  'docs/generated/legacy-doc-audit.md',
  'docs/generated/context-contract-report.md',
  'docs/generated/context-efficiency-report.md',
  'docs/generated/contextual-retrieval.md',
  'docs/generated/contextual-retrieval-index.json',
  'docs/generated/agent-catalog.md',
  'docs/generated/agent-catalog.json',
  'docs/generated/tool-catalog.md',
  'docs/generated/tool-catalog.json',
  'docs/generated/agent-usage-report.md',
  'docs/generated/agent-usage-report.json',
  'docs/generated/context-registry.md',
  'docs/generated/context-registry.json',
  'docs/generated/context-ab-report.md',
  'docs/generated/sandbox-policy-report.md',
  'docs/generated/context-value-demo.md',
  'docs/generated/context-value-demo.json',
  'docs/generated/claude-compatibility-bootstrap.md',
]);

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function read(filePath) {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : '';
}

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[docs:governance] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.writeFileSync(filePath, content);
}

function walk(dir) {
  if (!dir || !fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(fullPath));
      continue;
    }
    files.push(fullPath);
  }
  return files;
}

function normalize(relPath) {
  return relPath.split(path.sep).join('/');
}

function loadConfig() {
  if (!fs.existsSync(configPath)) return {};
  return JSON.parse(read(configPath));
}

function classify(relPath) {
  const exact = {
    'docs/README.md': ['canonical-entry', 'canonical', 'Task-level docs router.'],
    'docs/SYSTEM_INTENT.md': ['canonical-entry', 'canonical', 'Canonical system intent and invariants.'],
    'docs/CONTEXT_ENGINEERING.md': ['canonical-entry', 'canonical', 'Canonical context-layering and retrieval discipline doc.'],
    'docs/CONTEXT_EVALUATION.md': ['canonical-entry', 'canonical', 'Canonical context evaluation and measurement doc.'],
    'docs/CLAUDE_COMPATIBILITY.md': ['canonical-entry', 'canonical', 'Canonical Claude-native compatibility doc.'],
    'docs/CONTEXT_PLATFORM.md': ['canonical-entry', 'canonical', 'Canonical platform and registry doc.'],
    'docs/CONTEXTUAL_RETRIEVAL.md': ['canonical-entry', 'canonical', 'Canonical contextual retrieval doc.'],
    'docs/AGENT_FACTORY.md': ['canonical-entry', 'canonical', 'Canonical agent blueprint and scaffolding doc.'],
    'docs/TOOL_DESIGN.md': ['canonical-entry', 'canonical', 'Canonical tool contract design doc.'],
    'docs/AGENT_OBSERVABILITY.md': ['canonical-entry', 'canonical', 'Canonical runtime telemetry and value-evidence doc.'],
    'docs/MULTI_AGENT_COORDINATION.md': ['canonical-entry', 'canonical', 'Canonical multi-agent ownership and conflict-control doc.'],
    'docs/SANDBOX_POLICY.md': ['canonical-entry', 'canonical', 'Canonical sandbox boundary doc.'],
    'docs/DESIGN.md': ['canonical-entry', 'canonical', 'Canonical design router.'],
    'docs/ENGINEERING.md': ['canonical-entry', 'canonical', 'Canonical engineering/state authority router.'],
    'docs/PLANS.md': ['canonical-entry', 'canonical', 'Canonical plans router.'],
    'docs/PRODUCT_SENSE.md': ['canonical-entry', 'canonical', 'Canonical product heuristics router.'],
    'docs/QUALITY_SCORE.md': ['canonical-entry', 'canonical', 'Canonical quality scorecard.'],
    'docs/RELIABILITY.md': ['canonical-entry', 'canonical', 'Canonical reliability router.'],
    'docs/SECURITY.md': ['canonical-entry', 'canonical', 'Canonical security router.'],
    'docs/HARNESS.md': ['canonical-entry', 'canonical', 'Canonical harness router.'],
    'docs/AGENT_CONTEXT_PROTOCOL.md': ['runtime-protocol', 'canonical', 'Context memory and handoff contract.'],
    'docs/AGENT_WATCH_LOG.md': ['ops-log', 'historical', 'Operational evidence log.'],
  };
  if (exact[relPath]) return exact[relPath];
  if (relPath === 'docs/archive/README.md') return ['archive-router', 'tracked-only', 'Archive interpretation policy.'];
  if (relPath === '.claude/README.md') return ['claude-router', 'canonical', 'Claude-native router.'];
  if (relPath === '.claude/agents/README.md') return ['claude-agent-router', 'canonical', 'Claude subagent router.'];
  if (relPath === '.claude/commands/README.md') return ['claude-command-router', 'canonical', 'Claude command router.'];
  if (relPath === '.claude/hooks/README.md') return ['claude-hook-router', 'canonical', 'Claude hook router.'];
  if (relPath === 'agents/README.md') return ['agent-router', 'canonical', 'Agent manifest authoring router.'];
  if (relPath === 'tools/README.md') return ['tool-router', 'canonical', 'Tool manifest authoring router.'];
  if (relPath.startsWith('.claude/agents/')) return ['claude-agent', 'canonical', 'Claude subagent artifact.'];
  if (relPath.startsWith('.claude/commands/')) return ['claude-command', 'canonical', 'Claude slash-command artifact.'];
  if (relPath.startsWith('.claude/hooks/')) return ['claude-hook', 'supporting', 'Claude hook artifact.'];
  if (relPath.startsWith('docs/archive/')) return ['archive', 'tracked-only', 'Historical artifact only.'];
  if (relPath.startsWith('docs/design-docs/')) return ['design-doc', 'canonical', 'Structured design document.'];
  if (relPath.startsWith('docs/product-specs/')) return ['product-spec', 'canonical', 'Structured surface spec.'];
  if (relPath.startsWith('docs/exec-plans/active/')) return ['active-plan', 'canonical', 'Active execution plan.'];
  if (relPath.startsWith('docs/exec-plans/completed/')) return ['completed-plan', 'historical', 'Completed execution plan.'];
  if (relPath.startsWith('docs/exec-plans/')) return ['plans-support', 'canonical', 'Planning support doc.'];
  if (relPath.startsWith('docs/generated/')) return ['generated', 'generated', 'Generated artifact.'];
  if (relPath.startsWith('docs/references/')) return ['reference', 'supporting', 'Reference shelf.'];
  return ['unclassified', 'unknown', 'Needs promotion or archive placement.'];
}

function extractRefs(content) {
  const refs = [];
  const capture = (value) => {
    const trimmed = value.trim().replace(/[.,;:]$/, '');
    if (
      trimmed === 'README.md' ||
      trimmed === 'AGENTS.md' ||
      trimmed === 'CLAUDE.md' ||
      trimmed === 'ARCHITECTURE.md' ||
      trimmed === 'context-kit.json' ||
      trimmed.startsWith('.claude/') ||
      trimmed.endsWith('/CLAUDE.md') ||
      trimmed.startsWith('agents/') ||
      trimmed.startsWith('tools/') ||
      trimmed.startsWith('docs/') ||
      trimmed.startsWith('scripts/') ||
      trimmed.startsWith('prompts/') ||
      trimmed.startsWith('lint/') ||
      trimmed.startsWith('src/') ||
      trimmed.startsWith('.githooks/')
    ) refs.push(trimmed);
  };

  for (const match of content.matchAll(/`([^`]+)`/g)) capture(match[1]);
  for (const match of content.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) capture(match[1]);
  return [...new Set(refs)];
}

function existsRepoPath(candidate) {
  if (candidate.includes('*')) return true;
  if (virtualExistingRefs.has(candidate)) return true;
  return fs.existsSync(path.join(rootDir, candidate));
}

function parseContracts(filePath) {
  const content = read(path.join(rootDir, filePath));
  const lines = content.split('\n');
  const start = lines.findIndex((line) => line.trim() === '## Context Contracts');
  if (start === -1) return { missing: true, routes: [], stores: [], apis: [] };

  const sections = { routes: [], stores: [], apis: [] };
  let current = null;
  for (let i = start + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (line.startsWith('## ') && line !== '## Context Contracts') break;
    if (line === '### Routes') current = 'routes';
    else if (line === '### Stores') current = 'stores';
    else if (line === '### APIs') current = 'apis';
    else if (line.startsWith('- ') && current) {
      const match = line.match(/^- `?([^`]+)`?/);
      if (match) sections[current].push(match[1]);
    }
  }

  return { missing: false, ...sections };
}

function discoverFromConfigAndCode() {
  const config = loadConfig();
  const routes = new Set();
  const stores = new Set();
  const apis = new Set();

  const routesDir = config.discovery?.routesDir ? path.join(rootDir, config.discovery.routesDir) : null;
  const storesDir = config.discovery?.storesDir ? path.join(rootDir, config.discovery.storesDir) : null;
  const apiDir = config.discovery?.apiDir ? path.join(rootDir, config.discovery.apiDir) : null;

  for (const file of walk(routesDir)) {
    const rel = normalize(path.relative(routesDir, file));
    if (/\/\+page\.(svelte|ts|js|tsx|jsx)$/.test(rel) || /^\+page\.(svelte|ts|js|tsx|jsx)$/.test(rel)) {
      const route = rel.replace(/\/\+page\.(svelte|ts|js|tsx|jsx)$/, '').replace(/^\+page\.(svelte|ts|js|tsx|jsx)$/, '');
      routes.add(route ? `/${route}` : '/');
    }
  }

  for (const file of walk(storesDir)) {
    const ext = path.extname(file);
    if (['.ts', '.js', '.mjs', '.cjs', '.py'].includes(ext)) {
      stores.add(path.basename(file, ext));
    }
  }

  for (const file of walk(apiDir)) {
    const rel = normalize(path.relative(apiDir, file));
    if (/\/\+server\.(ts|js)$/.test(rel) || /^\+server\.(ts|js)$/.test(rel)) {
      const route = rel.replace(/\/\+server\.(ts|js)$/, '').replace(/^\+server\.(ts|js)$/, '');
      apis.add(`/api/${route}`.replace(/\/+/g, '/'));
    }
  }

  for (const surface of config.surfaces ?? []) {
    for (const route of surface.routes ?? []) routes.add(route);
    for (const store of surface.stores ?? []) stores.add(store);
    for (const api of surface.apis ?? []) apis.add(api);
  }

  return { config, routes, stores, apis };
}

const { config, routes, stores, apis } = discoverFromConfigAndCode();
ensureDir(generatedDir);

const markdownFiles = [
  ...['README.md', 'AGENTS.md', 'CLAUDE.md', 'ARCHITECTURE.md', '.claude/README.md']
    .map((file) => path.join(rootDir, file))
    .filter((file) => fs.existsSync(file)),
  ...walk(path.join(rootDir, 'agents'))
    .filter((file) => file.endsWith('.md')),
  ...walk(path.join(rootDir, 'tools'))
    .filter((file) => file.endsWith('.md')),
  ...walk(docsDir)
    .filter((file) => file.endsWith('.md'))
    .filter((file) => !generatedSelfRefs.has(normalize(path.relative(rootDir, file)))),
];

const catalogRows = [];
const auditRows = [];

for (const file of markdownFiles) {
  const relPath = normalize(path.relative(rootDir, file));
  const [status, authority, note] = classify(relPath);
  catalogRows.push(`| \`${relPath}\` | \`${status}\` | \`${authority}\` | ${note} |`);

  const content = read(file);
  for (const ref of extractRefs(content)) {
    if (!existsRepoPath(ref)) {
      auditRows.push(`| \`${relPath}\` | broken-ref | \`${ref}\` | fail |`);
    }
  }

  const lines = content.split('\n');
  const patterns = [
    ['absolute-local-path', /(?:\/Users\/|\/tmp\/|\/var\/folders\/)[^\s`)]*/g],
    ['parent-relative-ref', /\.\.\/[A-Za-z0-9._/-]+/g],
    ['unrendered-placeholder', /__(?:PROJECT|MAIN|TODAY)_[A-Z_]+__/g],
  ];
  lines.forEach((line, index) => {
    for (const [kind, pattern] of patterns) {
      for (const match of line.matchAll(pattern)) {
        auditRows.push(`| \`${relPath}:${index + 1}\` | ${kind} | \`${match[0]}\` | tracked |`);
      }
    }
  });
}

const contractRows = [];
for (const surface of config.surfaces ?? []) {
  if (!surface.spec) continue;
  if (!fs.existsSync(path.join(rootDir, surface.spec))) {
    contractRows.push(`| \`${surface.id}\` | spec-missing | \`${surface.spec}\` | fail |`);
    continue;
  }
  const contracts = parseContracts(surface.spec);
  if (contracts.missing) {
    contractRows.push(`| \`${surface.id}\` | contracts-missing | \`${surface.spec}\` | fail |`);
    continue;
  }
  for (const route of contracts.routes) {
    contractRows.push(`| \`${surface.id}\` | route | \`${route}\` | ${routes.has(route) ? 'ok' : 'missing'} |`);
  }
  for (const store of contracts.stores) {
    if (store === 'none') continue;
    contractRows.push(`| \`${surface.id}\` | store | \`${store}\` | ${stores.has(store) ? 'ok' : 'missing'} |`);
  }
  for (const api of contracts.apis) {
    if (api === 'none') continue;
    contractRows.push(`| \`${surface.id}\` | api | \`${api}\` | ${apis.has(api) ? 'ok' : 'missing'} |`);
  }
}

writeManaged(
  path.join(generatedDir, 'docs-catalog.md'),
  [
    '# Docs Catalog',
    '',
    '| Path | Status | Authority | Note |',
    '| --- | --- | --- | --- |',
    ...catalogRows.sort(),
    '',
  ].join('\n'),
);

writeManaged(
  path.join(generatedDir, 'legacy-doc-audit.md'),
  [
    '# Legacy Doc Audit',
    '',
    '| Location | Kind | Value | Severity |',
    '| --- | --- | --- | --- |',
    ...(auditRows.length ? auditRows.sort() : ['| none | none | none | ok |']),
    '',
  ].join('\n'),
);

writeManaged(
  path.join(generatedDir, 'context-contract-report.md'),
  [
    '# Context Contract Report',
    '',
    '| Surface | Kind | Value | Status |',
    '| --- | --- | --- | --- |',
    ...(contractRows.length ? contractRows.sort() : ['| none | none | none | ok |']),
    '',
  ].join('\n'),
);
