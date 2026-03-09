#!/usr/bin/env node
import http from 'node:http';
import path from 'node:path';
import { describeManifestEntry, readJson, registryPath, searchManifest } from './context-registry-lib.mjs';
import { scoreRetrieval } from './context-retrieval-lib.mjs';

const rootDir = process.cwd();
const config = readJson(path.join(rootDir, 'context-kit.json'));
const manifestPath = registryPath(rootDir, config.registry?.manifestPath);
const retrievalIndexPath = path.join(rootDir, config.retrieval?.indexPath ?? 'docs/generated/contextual-retrieval-index.json');
const telemetryReportPath = path.join(rootDir, config.telemetry?.reportPath ?? 'docs/generated/agent-usage-report.json');
const host = process.env.CONTEXT_REGISTRY_HOST || '127.0.0.1';
const port = Number(process.env.CONTEXT_REGISTRY_PORT || 4317);

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, { 'content-type': 'application/json; charset=utf-8' });
  response.end(`${JSON.stringify(payload, null, 2)}\n`);
}

const server = http.createServer((request, response) => {
  const url = new URL(request.url || '/', `http://${host}:${port}`);
  const manifest = readJson(manifestPath);
  const retrievalIndex = readJson(retrievalIndexPath);

  if (url.pathname === '/healthz') {
    sendJson(response, 200, { ok: true });
    return;
  }

  if (url.pathname === '/manifest') {
    sendJson(response, 200, manifest);
    return;
  }

  if (url.pathname === '/agents') {
    sendJson(response, 200, {
      results: manifest.agents ?? [],
    });
    return;
  }

  if (url.pathname === '/tools') {
    sendJson(response, 200, {
      results: manifest.tools ?? [],
    });
    return;
  }

  if (url.pathname === '/agent-usage') {
    sendJson(response, 200, readJson(telemetryReportPath));
    return;
  }

  if (url.pathname === '/search') {
    const query = url.searchParams.get('q') ?? '';
    const kind = url.searchParams.get('kind') ?? 'all';
    const limit = Number(url.searchParams.get('limit') ?? 10);
    sendJson(response, 200, {
      query,
      kind,
      results: searchManifest(manifest, { query, kind, limit }),
    });
    return;
  }

  if (url.pathname === '/describe') {
    const kind = url.searchParams.get('kind') ?? 'all';
    const id = url.searchParams.get('id') ?? '';
    const entryPath = url.searchParams.get('path') ?? '';
    const title = url.searchParams.get('title') ?? '';
    const result = describeManifestEntry(manifest, {
      kind,
      id,
      path: entryPath,
      title,
    });
    if (!result) {
      sendJson(response, 404, { error: 'not_found' });
      return;
    }
    sendJson(response, 200, result);
    return;
  }

  if (url.pathname === '/retrieve') {
    const query = url.searchParams.get('q') ?? '';
    const surface = url.searchParams.get('surface') ?? '';
    const pathPrefix = url.searchParams.get('path') ?? '';
    const top = Number(url.searchParams.get('top') ?? (config.retrieval?.defaultTopK ?? 5));
    sendJson(response, 200, {
      query,
      surface,
      path: pathPrefix,
      results: scoreRetrieval(retrievalIndex, query, {
        topK: top,
        surface,
        path: pathPrefix,
      }),
    });
    return;
  }

  sendJson(response, 404, { error: 'not_found' });
});

server.listen(port, host, () => {
  console.log(`[registry:serve] listening on http://${host}:${port}`);
  console.log('[registry:serve] endpoints: /healthz, /manifest, /agents, /tools, /agent-usage, /search?q=<term>&kind=agent, /describe?kind=tool&id=context-retrieve, /retrieve?q=<term>');
});
