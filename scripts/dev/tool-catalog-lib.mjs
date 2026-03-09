#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { readJson } from './context-registry-lib.mjs';
import { relativeToRoot, toPosix } from './agent-catalog-lib.mjs';

function isSafeRepoPath(value) {
  if (!value) return false;
  if (value.startsWith('/')) return false;
  if (value.includes('..')) return false;
  return true;
}

export function loadToolConfig(rootDir) {
  const config = readJson(path.join(rootDir, 'context-kit.json'));
  const surfaces = (config.surfaces ?? []).map((surface) => surface.id);
  const toolConfig = config.tools ?? {};
  return {
    config,
    surfaces,
    toolConfig: {
      dir: toolConfig.dir ?? 'tools',
      catalogPath: toolConfig.catalogPath ?? 'docs/generated/tool-catalog.json',
      enabled: toolConfig.enabled ?? true,
      defaultSurface: toolConfig.defaultSurface ?? surfaces[0] ?? 'core',
    },
  };
}

export function toolDir(rootDir) {
  const { toolConfig } = loadToolConfig(rootDir);
  return path.join(rootDir, toolConfig.dir);
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

function isHttpMethod(value) {
  return ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(String(value ?? '').toUpperCase());
}

function isInvocationValid(invocation) {
  if (!invocation || typeof invocation !== 'object') return false;
  if (invocation.kind === 'npm-script') {
    return String(invocation.script ?? '').trim().length > 0;
  }
  if (invocation.kind === 'http') {
    return isHttpMethod(invocation.method) && String(invocation.path ?? '').startsWith('/');
  }
  return false;
}

export function validateToolManifest(rootDir, manifest, knownSurfaces) {
  const issues = [];
  const required = ['id', 'name', 'summary', 'scope'];
  for (const field of required) {
    if (!String(manifest[field] ?? '').trim()) {
      issues.push(`missing required field: ${field}`);
    }
  }

  if (!/^[a-z0-9][a-z0-9-]*$/.test(String(manifest.id ?? ''))) {
    issues.push('id must match ^[a-z0-9][a-z0-9-]*$');
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

  if (!Array.isArray(manifest.inputs) || manifest.inputs.length === 0) {
    issues.push('inputs must be a non-empty array');
  }
  if (!Array.isArray(manifest.outputs) || manifest.outputs.length === 0) {
    issues.push('outputs must be a non-empty array');
  }

  if (!isInvocationValid(manifest.invocation)) {
    issues.push('invocation must define a valid npm-script or http contract');
  }

  if (!manifest.safety || typeof manifest.safety !== 'object') {
    issues.push('safety must be an object');
  } else {
    if (!['read-only', 'writes-repo', 'writes-generated', 'external-side-effects'].includes(String(manifest.safety.sideEffects ?? ''))) {
      issues.push('safety.sideEffects must be one of read-only|writes-repo|writes-generated|external-side-effects');
    }
  }

  for (const repoPath of manifest.reads ?? []) {
    if (!pathLooksResolvable(rootDir, repoPath)) {
      issues.push(`read path is missing or invalid: ${repoPath}`);
    }
  }

  for (const repoPath of manifest.writes ?? []) {
    if (!pathLooksResolvable(rootDir, repoPath)) {
      issues.push(`write path is missing or invalid: ${repoPath}`);
    }
  }

  return issues;
}

export function loadToolManifests(rootDir) {
  const { surfaces, toolConfig } = loadToolConfig(rootDir);
  const knownSurfaces = new Set(surfaces);
  const dirPath = path.join(rootDir, toolConfig.dir);
  if (!fs.existsSync(dirPath)) return [];

  return fs.readdirSync(dirPath)
    .filter((entry) => entry.endsWith('.json'))
    .sort((left, right) => left.localeCompare(right))
    .map((entry) => {
      const manifestPath = path.join(dirPath, entry);
      const manifest = readJson(manifestPath);
      const issues = validateToolManifest(rootDir, manifest, knownSurfaces);
      return {
        ...manifest,
        manifestPath: relativeToRoot(rootDir, manifestPath),
        issues,
        valid: issues.length === 0,
      };
    });
}

export function loadValidTools(rootDir) {
  const manifests = loadToolManifests(rootDir);
  const invalid = manifests.filter((item) => !item.valid);
  if (invalid.length > 0) {
    const details = invalid
      .map((item) => `${item.manifestPath}: ${item.issues.join('; ')}`)
      .join('\n');
    throw new Error(`[tool-catalog] invalid manifests:\n${details}`);
  }
  return manifests.map((item) => ({
    ...item,
    reads: (item.reads ?? []).map((value) => toPosix(value)),
    writes: (item.writes ?? []).map((value) => toPosix(value)),
  }));
}
