#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const configPath = path.join(rootDir, 'context-kit.json');
const generatedDir = path.join(rootDir, 'docs', 'generated');
const routesPath = path.join(generatedDir, 'route-map.md');
const storesPath = path.join(generatedDir, 'store-authority-map.md');
const apisPath = path.join(generatedDir, 'api-group-map.md');
const guidePath = path.join(generatedDir, 'project-truth-bootstrap.md');
const usageReportPath = path.join(generatedDir, 'agent-usage-report.json');
const today = new Date().toISOString().slice(0, 10);

function readText(filePath) {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : '';
}

function writeText(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

function loadJson(filePath, fallback) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function toListLines(values) {
  if (!values.length) return ['- none'];
  return values.map((value) => `- \`${value}\``);
}

function parseTableFirstColumn(filePath) {
  const lines = readText(filePath).split('\n');
  const results = [];
  for (const line of lines) {
    const match = /^\| `([^`]+)` \|/.exec(line.trim());
    if (match) results.push(match[1]);
  }
  return [...new Set(results)];
}

function parseApiEntries(filePath) {
  const lines = readText(filePath).split('\n');
  const results = [];
  for (const line of lines) {
    const match = /^\| `([^`]+)` \|/.exec(line.trim());
    if (match) results.push(match[1]);
  }
  return [...new Set(results)];
}

function tokenizeSurface(surfaceId) {
  const lower = surfaceId.toLowerCase();
  return [...new Set([lower, lower.replace(/[^a-z0-9]/g, '')].filter(Boolean))];
}

function routeBelongsToSurface(route, surfaceId, firstSurfaceId, totalSurfaces) {
  if (totalSurfaces === 1) return true;
  if (route === '/') return surfaceId === firstSurfaceId;
  const prefix = `/${surfaceId}`;
  return route === prefix || route.startsWith(`${prefix}/`);
}

function storeBelongsToSurface(store, surfaceId) {
  const lower = store.toLowerCase();
  return tokenizeSurface(surfaceId).some((token) => token && lower.includes(token));
}

function apiBelongsToSurface(api, surfaceId) {
  const prefix = `/api/${surfaceId}`;
  return api === prefix || api.startsWith(`${prefix}/`);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function replaceSection(text, heading, nextHeading, values) {
  const replacement = `${heading}\n${toListLines(values).join('\n')}\n\n`;
  const pattern = new RegExp(`(${escapeRegExp(heading)}\\n)([\\s\\S]*?)(?=${escapeRegExp(nextHeading)}\\n)`, 'm');
  if (pattern.test(text)) {
    return text.replace(pattern, replacement);
  }
  return text;
}

function syncSpecDoc(specPath, surface) {
  if (!fs.existsSync(specPath)) return false;
  let text = readText(specPath);
  const original = text;
  const routeEntry = surface.routes[0] ?? 'n/a';
  text = text.replace(/^- Canonical route entry: `[^`]*`$/m, `- Canonical route entry: \`${routeEntry}\``);
  text = replaceSection(text, '### Routes', '### Stores', surface.routes);
  text = replaceSection(text, '### Stores', '### APIs', surface.stores);
  text = replaceSection(text, '### APIs', '## Deep Links', surface.apis);
  if (text !== original) {
    writeText(specPath, text);
    return true;
  }
  return false;
}

function ensureEngineeringInventory(engineeringPath, rows, unmapped) {
  if (!fs.existsSync(engineeringPath)) return false;
  const startMarker = '<!-- BEGIN MEMENTO MANAGED INVENTORY -->';
  const endMarker = '<!-- END MEMENTO MANAGED INVENTORY -->';
  const block = [
    '## Current Inventory Snapshot',
    startMarker,
    `Refreshed: \`${today}\``,
    '',
    '| Surface | Routes | Stores | APIs | Mapping Mode |',
    '| --- | --- | --- | --- | --- |',
    ...rows,
    '',
    '### Unmapped Discovered Routes',
    ...toListLines(unmapped.routes),
    '',
    '### Unmapped Discovered Stores',
    ...toListLines(unmapped.stores),
    '',
    '### Unmapped Discovered APIs',
    ...toListLines(unmapped.apis),
    '',
    'Review this snapshot, then replace the placeholder language in `State Authority` with project-specific rules.',
    endMarker,
    '',
  ].join('\n');

  const original = readText(engineeringPath);
  let next = original;
  const managedBlock = new RegExp(
    `## Current Inventory Snapshot\\n\\s*${escapeRegExp(startMarker)}[\\s\\S]*?${escapeRegExp(endMarker)}\\n?`,
    'm',
  );

  if (managedBlock.test(original)) {
    next = original.replace(managedBlock, block);
  } else if (original.startsWith('# ')) {
    const firstBreak = original.indexOf('\n');
    next = `${original.slice(0, firstBreak + 1)}\n${block}${original.slice(firstBreak + 1)}`.replace(/\n{3,}/g, '\n\n');
  } else {
    next = `${block}${original}`;
  }

  if (next !== original) {
    writeText(engineeringPath, next);
    return true;
  }
  return false;
}

const config = loadJson(configPath, {});
const surfaces = Array.isArray(config.surfaces) ? config.surfaces : [];
const allRoutes = parseTableFirstColumn(routesPath);
const allStores = parseTableFirstColumn(storesPath);
const allApis = parseApiEntries(apisPath);
const firstSurfaceId = surfaces[0]?.id ?? null;

let configChanged = false;
let syncedSpecs = 0;
const mappingRows = [];

for (const surface of surfaces) {
  const originalRoutes = Array.isArray(surface.routes) ? [...surface.routes] : [];
  const originalStores = Array.isArray(surface.stores) ? [...surface.stores] : [];
  const originalApis = Array.isArray(surface.apis) ? [...surface.apis] : [];
  let mode = 'manual-preserved';

  if (!originalRoutes.length) {
    surface.routes = allRoutes.filter((route) =>
      routeBelongsToSurface(route, surface.id, firstSurfaceId, surfaces.length),
    );
    mode = surfaces.length === 1 ? 'auto-seeded-all' : 'auto-seeded-heuristic';
  }

  if (!originalStores.length) {
    surface.stores = allStores.filter((store) => storeBelongsToSurface(store, surface.id));
    if (mode === 'manual-preserved') {
      mode = surfaces.length === 1 ? 'auto-seeded-all' : 'auto-seeded-heuristic';
    }
  }

  if (!originalApis.length) {
    surface.apis = allApis.filter((api) => apiBelongsToSurface(api, surface.id));
    if (mode === 'manual-preserved') {
      mode = surfaces.length === 1 ? 'auto-seeded-all' : 'auto-seeded-heuristic';
    }
  }

  if (JSON.stringify(originalRoutes) !== JSON.stringify(surface.routes)
    || JSON.stringify(originalStores) !== JSON.stringify(surface.stores)
    || JSON.stringify(originalApis) !== JSON.stringify(surface.apis)) {
    configChanged = true;
  }

  const specPath = path.join(rootDir, surface.spec ?? `docs/product-specs/${surface.id}.md`);
  if (syncSpecDoc(specPath, surface)) {
    syncedSpecs += 1;
  }

  mappingRows.push(
    `| \`${surface.id}\` | ${surface.routes.length} | ${surface.stores.length} | ${surface.apis.length} | ${mode} |`,
  );
}

if (configChanged) {
  writeText(configPath, `${JSON.stringify(config, null, 2)}\n`);
}

const mappedRoutes = new Set(surfaces.flatMap((surface) => surface.routes ?? []));
const mappedStores = new Set(surfaces.flatMap((surface) => surface.stores ?? []));
const mappedApis = new Set(surfaces.flatMap((surface) => surface.apis ?? []));

const unmapped = {
  routes: allRoutes.filter((route) => !mappedRoutes.has(route)),
  stores: allStores.filter((store) => !mappedStores.has(store)),
  apis: allApis.filter((api) => !mappedApis.has(api)),
};

ensureEngineeringInventory(
  path.join(rootDir, 'docs', 'ENGINEERING.md'),
  mappingRows,
  unmapped,
);

const usageReport = loadJson(usageReportPath, { totals: { runs: 0, completedRuns: 0 } });
const runCount = usageReport?.totals?.runs ?? 0;
const completedRuns = usageReport?.totals?.completedRuns ?? 0;

const guide = [
  '# Project Truth Bootstrap',
  '',
  'This report explains what Memento Kit auto-seeded and what still needs real project knowledge from humans or agents.',
  '',
  '## Auto-Applied Bootstrap',
  '',
  `- Surfaces reviewed: \`${surfaces.length}\``,
  `- context-kit surface mappings updated: \`${configChanged ? 'yes' : 'no change'}\``,
  `- product spec contract sections refreshed: \`${syncedSpecs}\``,
  '- engineering inventory snapshot refreshed: `yes`',
  '',
  '| Surface | Routes | Stores | APIs | Mapping Mode |',
  '| --- | --- | --- | --- | --- |',
  ...(mappingRows.length ? mappingRows : ['| none | 0 | 0 | 0 | none |']),
  '',
  '## Manual Fill Priorities',
  '',
  '1. `docs/ENGINEERING.md`',
  '   - Replace the placeholder text in `State Authority` with real ownership rules.',
  '   - Use `docs/generated/route-map.md`, `docs/generated/store-authority-map.md`, and `docs/generated/api-group-map.md` as evidence.',
  '2. `docs/PRODUCT_SENSE.md`',
  '   - Replace generic heuristics with actual user-value and scope rules.',
  '3. `docs/product-specs/*.md`',
  '   - The route/store/api contract lists are now seeded, but `Purpose`, `Done Means`, and `Deep Links` still need project truth.',
  '4. `docs/CLAUDE_COMPATIBILITY.md` and any local `CLAUDE.md` files created near risky directories',
  '   - Replace placeholder local-risk language with concrete hazards, checks, and escalation rules.',
  '5. `README.md`, `ARCHITECTURE.md`, and `docs/design-docs/*.md`',
  '   - Promote stable design and implementation decisions there when they are no longer task-local.',
  '',
  '## Remaining Gaps',
  '',
  `- Unmapped discovered routes: \`${unmapped.routes.length}\``,
  `- Unmapped discovered stores: \`${unmapped.stores.length}\``,
  `- Unmapped discovered APIs: \`${unmapped.apis.length}\``,
  `- Telemetry runs recorded: \`${runCount}\` total / \`${completedRuns}\` completed`,
  '',
  '### Unmapped Routes',
  ...toListLines(unmapped.routes),
  '',
  '### Unmapped Stores',
  ...toListLines(unmapped.stores),
  '',
  '### Unmapped APIs',
  ...toListLines(unmapped.apis),
  '',
  '## Suggested Next Commands',
  '',
  '- `npm run docs:refresh`',
  '- `npm run docs:check`',
  '- `npm run claude:bootstrap`',
  '- `npm run value:demo`',
  '- `npm run agent:start -- --agent planner --surface <surface>`',
  '- `npm run agent:finish -- --status success --baseline-minutes <n>`',
  '',
  '## Fast Interpretation',
  '',
  '- Auto-seeded route/store/api mappings reduce empty skeleton docs.',
  '- This report is not a substitute for real project truth in canonical docs.',
  '- Value claims become stronger once telemetry and routed-vs-baseline evidence are recorded.',
  '',
];

writeText(guidePath, `${guide.join('\n')}\n`);

process.stdout.write(`[bootstrap-project-truth] wrote ${path.relative(rootDir, guidePath)}\n`);
if (configChanged) {
  process.stdout.write('[bootstrap-project-truth] updated context-kit.json surface mappings\n');
}
if (syncedSpecs > 0) {
  process.stdout.write(`[bootstrap-project-truth] refreshed ${syncedSpecs} surface spec contract section(s)\n`);
}
