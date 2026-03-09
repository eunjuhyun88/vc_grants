#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const configPath = path.join(rootDir, 'context-kit.json');
const args = new Set(process.argv.slice(2));
const checkMode = args.has('--check');

function loadConfig() {
  if (!fs.existsSync(configPath)) return {};
  return JSON.parse(fs.readFileSync(configPath, 'utf8'));
}

function toPosix(value) {
  return value.split(path.sep).join('/');
}

function walkFiles(dir) {
  if (!dir || !fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkFiles(entryPath));
      continue;
    }
    files.push(entryPath);
  }
  return files;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[docs:refresh] stale generated file: ${toPosix(path.relative(rootDir, filePath))}`);
    }
    return;
  }
  fs.writeFileSync(filePath, content);
}

const config = loadConfig();
const discovery = config.discovery ?? {};
const routesDir = discovery.routesDir ? path.join(rootDir, discovery.routesDir) : null;
const storesDir = discovery.storesDir ? path.join(rootDir, discovery.storesDir) : null;
const apiDir = discovery.apiDir ? path.join(rootDir, discovery.apiDir) : null;
const generatedDir = path.join(rootDir, 'docs/generated');
ensureDir(generatedDir);

function discoverRoutes() {
  const discovered = new Map();
  for (const file of walkFiles(routesDir)) {
    const rel = toPosix(path.relative(routesDir, file));
    let route = null;
    if (/\/\+page\.(svelte|ts|js|tsx|jsx)$/.test(rel) || /^\+page\.(svelte|ts|js|tsx|jsx)$/.test(rel)) {
      route = rel.replace(/\/\+page\.(svelte|ts|js|tsx|jsx)$/, '').replace(/^\+page\.(svelte|ts|js|tsx|jsx)$/, '');
    } else if (/\/index\.(tsx|jsx|mdx|html)$/.test(rel) || /^index\.(tsx|jsx|mdx|html)$/.test(rel)) {
      route = rel.replace(/\/index\.(tsx|jsx|mdx|html)$/, '').replace(/^index\.(tsx|jsx|mdx|html)$/, '');
    }
    if (route == null) continue;
    const normalized = route ? `/${route}` : '/';
    discovered.set(normalized, toPosix(path.relative(rootDir, file)));
  }
  return discovered;
}

function discoverStores() {
  const discovered = new Map();
  for (const file of walkFiles(storesDir)) {
    const ext = path.extname(file);
    if (!['.ts', '.js', '.mjs', '.cjs', '.py'].includes(ext)) continue;
    const name = path.basename(file, ext);
    discovered.set(name, toPosix(path.relative(rootDir, file)));
  }
  return discovered;
}

function discoverApis() {
  const discovered = new Map();
  for (const file of walkFiles(apiDir)) {
    const rel = toPosix(path.relative(apiDir, file));
    let route = null;
    if (/\/\+server\.(ts|js)$/.test(rel) || /^\+server\.(ts|js)$/.test(rel)) {
      route = rel.replace(/\/\+server\.(ts|js)$/, '').replace(/^\+server\.(ts|js)$/, '');
    } else if (/\.(ts|js|py)$/.test(rel)) {
      route = rel.replace(/\.(ts|js|py)$/, '');
    }
    if (route == null) continue;
    discovered.set(`/api/${route}`.replace(/\/+/g, '/'), toPosix(path.relative(rootDir, file)));
  }
  return discovered;
}

const routeMap = discoverRoutes();
const storeMap = discoverStores();
const apiMap = discoverApis();

for (const surface of config.surfaces ?? []) {
  for (const route of surface.routes ?? []) {
    if (!routeMap.has(route)) routeMap.set(route, 'configured-only');
  }
  for (const store of surface.stores ?? []) {
    if (!storeMap.has(store)) storeMap.set(store, 'configured-only');
  }
  for (const api of surface.apis ?? []) {
    if (!apiMap.has(api)) apiMap.set(api, 'configured-only');
  }
}

function owners(kind, value) {
  return (config.surfaces ?? [])
    .filter((surface) => Array.isArray(surface[kind]) && surface[kind].includes(value))
    .map((surface) => surface.id);
}

function sourceLabel(filePath) {
  return filePath === 'configured-only' ? 'configured-only' : 'discovered';
}

const routeRows = [...routeMap.entries()]
  .sort((a, b) => a[0].localeCompare(b[0]))
  .map(([route, file]) => `| \`${route}\` | ${sourceLabel(file)} | \`${file}\` | ${(owners('routes', route).join(', ') || 'none')} |`);

const storeRows = [...storeMap.entries()]
  .sort((a, b) => a[0].localeCompare(b[0]))
  .map(([store, file]) => `| \`${store}\` | ${sourceLabel(file)} | \`${file}\` | ${(owners('stores', store).join(', ') || 'none')} |`);

const apiGroups = new Map();
for (const [api, file] of [...apiMap.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
  const segment = api.split('/').filter(Boolean)[1] || 'root';
  if (!apiGroups.has(segment)) apiGroups.set(segment, []);
  apiGroups.get(segment).push({ api, file, surfaceOwners: owners('apis', api) });
}

writeManaged(
  path.join(generatedDir, 'route-map.md'),
  [
    '# Route Map',
    '',
    '## App Routes',
    '',
    '| Route | Source | File | Surfaces |',
    '| --- | --- | --- | --- |',
    ...(routeRows.length ? routeRows : ['| none | none | none | none |']),
    '',
  ].join('\n'),
);

writeManaged(
  path.join(generatedDir, 'store-authority-map.md'),
  [
    '# Store Authority Map',
    '',
    '## Stores',
    '',
    '| Store | Source | File | Surfaces |',
    '| --- | --- | --- | --- |',
    ...(storeRows.length ? storeRows : ['| none | none | none | none |']),
    '',
  ].join('\n'),
);

const apiSections = ['# API Group Map', '', '## API Group Overview', ''];
if (apiGroups.size === 0) {
  apiSections.push('- none');
} else {
  for (const [group, entries] of apiGroups.entries()) {
    apiSections.push(`### ${group}`);
    apiSections.push('');
    apiSections.push('| API | Source | File | Surfaces |');
    apiSections.push('| --- | --- | --- | --- |');
    for (const entry of entries) {
      apiSections.push(`| \`${entry.api}\` | ${sourceLabel(entry.file)} | \`${entry.file}\` | ${(entry.surfaceOwners.join(', ') || 'none')} |`);
    }
    apiSections.push('');
  }
}

writeManaged(path.join(generatedDir, 'api-group-map.md'), `${apiSections.join('\n')}\n`);
