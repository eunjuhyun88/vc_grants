#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

export function readJson(filePath) {
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
}

export function registryPath(rootDir, configuredPath = 'docs/generated/context-registry.json') {
  return path.join(rootDir, configuredPath);
}

export function normalizedEntries(manifest, kind) {
  if (kind === 'surface') {
    return (manifest.surfaces ?? []).map((item) => ({
      kind,
      id: item.id,
      title: item.label || item.id,
      summary: item.summary || '',
      path: item.spec || '',
      payload: item,
    }));
  }

  if (kind === 'doc') {
    return (manifest.docs ?? []).map((item) => ({
      kind,
      id: item.path,
      title: item.role || item.path,
      summary: item.authority || '',
      path: item.path,
      payload: item,
    }));
  }

  if (kind === 'command') {
    return (manifest.commands ?? []).map((item) => ({
      kind,
      id: item.name,
      title: item.name,
      summary: item.category || '',
      path: item.script || '',
      payload: item,
    }));
  }

  if (kind === 'retrieval') {
    return (manifest.retrieval?.sources ?? []).map((item) => ({
      kind,
      id: item.path,
      title: item.path,
      summary: item.role || '',
      path: item.path,
      payload: item,
    }));
  }

  if (kind === 'agent') {
    return (manifest.agents ?? []).map((item) => ({
      kind,
      id: item.id,
      title: item.name || item.id,
      summary: item.summary || item.role || '',
      path: item.manifestPath || '',
      payload: item,
    }));
  }

  if (kind === 'tool') {
    return (manifest.tools ?? []).map((item) => ({
      kind,
      id: item.id,
      title: item.name || item.id,
      summary: item.summary || item.scope || '',
      path: item.manifestPath || '',
      payload: item,
    }));
  }

  return [];
}

export function manifestKinds() {
  return ['surface', 'doc', 'command', 'retrieval', 'agent', 'tool'];
}

export function manifestEntries(manifest, kind = 'all') {
  const kinds = kind === 'all' ? manifestKinds() : [kind];
  return kinds.flatMap((item) => normalizedEntries(manifest, item));
}

export function describeManifestEntry(manifest, options = {}) {
  const kind = options.kind ?? 'all';
  const id = String(options.id ?? '').trim();
  const path = String(options.path ?? '').trim();
  const title = String(options.title ?? '').trim().toLowerCase();
  const entries = manifestEntries(manifest, kind);
  const match = entries.find((entry) => {
    if (id && entry.id === id) return true;
    if (path && entry.path === path) return true;
    if (title && entry.title.toLowerCase() === title) return true;
    return false;
  });
  return match ?? null;
}

export function searchManifest(manifest, options = {}) {
  const query = String(options.query ?? '').trim().toLowerCase();
  const kind = options.kind ?? 'all';
  const limit = Number.isFinite(options.limit) && options.limit > 0 ? options.limit : 20;
  const entries = manifestEntries(manifest, kind);

  const scored = entries
    .map((entry) => {
      const haystack = [
        entry.id,
        entry.title,
        entry.summary,
        entry.path,
        JSON.stringify(entry.payload),
      ].join(' ').toLowerCase();
      const score = query
        ? (haystack.includes(query) ? (entry.id.toLowerCase() === query ? 3 : entry.title.toLowerCase().includes(query) ? 2 : 1) : 0)
        : 1;
      return { ...entry, score };
    })
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.kind.localeCompare(right.kind) || left.id.localeCompare(right.id));

  return scored.slice(0, limit);
}
