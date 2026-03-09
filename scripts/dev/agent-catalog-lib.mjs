#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { readJson } from './context-registry-lib.mjs';

export function toPosix(value) {
  return String(value).split(path.sep).join('/');
}

export function relativeToRoot(rootDir, filePath) {
  return toPosix(path.relative(rootDir, filePath));
}

export function loadAgentConfig(rootDir) {
  const config = readJson(path.join(rootDir, 'context-kit.json'));
  const surfaces = (config.surfaces ?? []).map((surface) => surface.id);
  const agentConfig = config.agents ?? {};
  return {
    config,
    surfaces,
    agentConfig: {
      dir: agentConfig.dir ?? 'agents',
      catalogPath: agentConfig.catalogPath ?? 'docs/generated/agent-catalog.json',
      enabled: agentConfig.enabled ?? true,
      defaultSurface: agentConfig.defaultSurface ?? surfaces[0] ?? 'core',
    },
  };
}

export function agentDir(rootDir) {
  const { agentConfig } = loadAgentConfig(rootDir);
  return path.join(rootDir, agentConfig.dir);
}

function isSafeRepoPath(value) {
  if (!value) return false;
  if (value.startsWith('/')) return false;
  if (value.includes('..')) return false;
  return true;
}

function pathLooksResolvable(rootDir, repoPath) {
  if (!isSafeRepoPath(repoPath)) return false;
  const fullPath = path.join(rootDir, repoPath);
  if (fs.existsSync(fullPath)) return true;
  let cursor = repoPath.endsWith('/') ? path.dirname(fullPath.replace(/\/+$/, '')) : path.dirname(fullPath);
  while (cursor && cursor !== rootDir && cursor !== path.dirname(cursor)) {
    if (fs.existsSync(cursor)) return true;
    cursor = path.dirname(cursor);
  }
  return fs.existsSync(rootDir);
}

export function validateAgentManifest(rootDir, manifest, knownSurfaces) {
  const issues = [];
  const required = ['id', 'name', 'role', 'summary', 'prompt', 'handoff'];
  for (const field of required) {
    if (!String(manifest[field] ?? '').trim()) {
      issues.push(`missing required field: ${field}`);
    }
  }

  if (!Array.isArray(manifest.surfaces) || manifest.surfaces.length === 0) {
    issues.push('surfaces must be a non-empty array');
  } else {
    for (const surface of manifest.surfaces) {
      if (!knownSurfaces.has(surface)) {
        issues.push(`unknown surface: ${surface}`);
      }
    }
  }

  for (const field of ['reads', 'writes', 'outputs']) {
    if (!Array.isArray(manifest[field]) || manifest[field].length === 0) {
      issues.push(`${field} must be a non-empty array`);
    }
  }

  for (const filePath of manifest.reads ?? []) {
    if (!pathLooksResolvable(rootDir, filePath)) {
      issues.push(`read path is missing or invalid: ${filePath}`);
    }
  }

  for (const filePath of manifest.writes ?? []) {
    if (!pathLooksResolvable(rootDir, filePath)) {
      issues.push(`write path is missing or invalid: ${filePath}`);
    }
  }

  if (!/^[a-z0-9][a-z0-9-]*$/.test(String(manifest.id ?? ''))) {
    issues.push('id must match ^[a-z0-9][a-z0-9-]*$');
  }

  return issues;
}

export function loadAgentManifests(rootDir) {
  const { surfaces, agentConfig } = loadAgentConfig(rootDir);
  const knownSurfaces = new Set(surfaces);
  const dirPath = path.join(rootDir, agentConfig.dir);
  if (!fs.existsSync(dirPath)) return [];

  return fs.readdirSync(dirPath)
    .filter((entry) => entry.endsWith('.json'))
    .sort((left, right) => left.localeCompare(right))
    .map((entry) => {
      const manifestPath = path.join(dirPath, entry);
      const manifest = readJson(manifestPath);
      const issues = validateAgentManifest(rootDir, manifest, knownSurfaces);
      return {
        ...manifest,
        manifestPath: relativeToRoot(rootDir, manifestPath),
        issues,
        valid: issues.length === 0,
      };
    });
}

export function loadValidAgents(rootDir) {
  const manifests = loadAgentManifests(rootDir);
  const invalid = manifests.filter((item) => !item.valid);
  if (invalid.length > 0) {
    const details = invalid
      .map((item) => `${item.manifestPath}: ${item.issues.join('; ')}`)
      .join('\n');
    throw new Error(`[agent-catalog] invalid manifests:\n${details}`);
  }
  return manifests;
}
