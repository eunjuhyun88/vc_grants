#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { readJson } from './context-registry-lib.mjs';
import { loadAgentManifests } from './agent-catalog-lib.mjs';

export function telemetryConfig(rootDir) {
  const config = readJson(path.join(rootDir, 'context-kit.json'));
  const telemetry = config.telemetry ?? {};
  return {
    config,
    telemetry: {
      enabled: telemetry.enabled ?? true,
      runsDir: telemetry.runsDir ?? '.agent-context/telemetry/runs',
      eventsDir: telemetry.eventsDir ?? '.agent-context/telemetry/events',
      activeDir: telemetry.activeDir ?? '.agent-context/telemetry/active',
      lockPath: telemetry.lockPath ?? '.agent-context/telemetry/telemetry.lock',
      lockStaleMinutes: Number(telemetry.lockStaleMinutes ?? 5),
      reportPath: telemetry.reportPath ?? 'docs/generated/agent-usage-report.json',
      defaults: {
        taskComplexity: telemetry.defaults?.taskComplexity ?? 'moderate',
        skillLevel: telemetry.defaults?.skillLevel ?? 'experienced',
        purpose: telemetry.defaults?.purpose ?? 'product-development',
        autonomy: telemetry.defaults?.autonomy ?? 'assisted',
      },
    },
  };
}

export function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function waitMs(milliseconds) {
  if (!Number.isFinite(milliseconds) || milliseconds <= 0) return;
  const signal = new Int32Array(new SharedArrayBuffer(4));
  Atomics.wait(signal, 0, 0, milliseconds);
}

export function currentBranch(rootDir) {
  try {
    return execSync('git rev-parse --abbrev-ref HEAD', {
      cwd: rootDir,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return 'detached-head';
  }
}

function safeName(value) {
  return String(value).replace(/[^A-Za-z0-9._-]+/g, '__');
}

function telemetryLockPath(rootDir) {
  const { telemetry } = telemetryConfig(rootDir);
  return path.join(rootDir, telemetry.lockPath);
}

export function runFilePath(rootDir, runId) {
  const { telemetry } = telemetryConfig(rootDir);
  return path.join(rootDir, telemetry.runsDir, `${runId}.json`);
}

export function eventFilePath(rootDir, runId) {
  const { telemetry } = telemetryConfig(rootDir);
  return path.join(rootDir, telemetry.eventsDir, `${runId}.jsonl`);
}

export function activeRunFilePath(rootDir, branch = currentBranch(rootDir)) {
  const { telemetry } = telemetryConfig(rootDir);
  return path.join(rootDir, telemetry.activeDir, `${safeName(branch)}.json`);
}

export function writeJson(filePath, value) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

export function withTelemetryLock(rootDir, fn) {
  const { telemetry } = telemetryConfig(rootDir);
  const lockPath = telemetryLockPath(rootDir);
  const staleThresholdMs = Math.max(1, telemetry.lockStaleMinutes) * 60_000;
  ensureDir(path.dirname(lockPath));

  let acquired = false;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      fs.writeFileSync(lockPath, `${JSON.stringify({
        pid: process.pid,
        createdAt: new Date().toISOString(),
      }, null, 2)}\n`, { flag: 'wx' });
      acquired = true;
      break;
    } catch (error) {
      if (error?.code !== 'EEXIST') {
        throw error;
      }
      const stat = fs.existsSync(lockPath) ? fs.statSync(lockPath) : null;
      const ageMs = stat ? Date.now() - stat.mtimeMs : 0;
      if (!stat || ageMs > staleThresholdMs) {
        try {
          fs.unlinkSync(lockPath);
        } catch {
          // Another process may have cleaned it first.
        }
        continue;
      }
      waitMs(50);
    }
  }

  if (!acquired) {
    throw new Error(`[agent-telemetry] telemetry lock busy: ${path.relative(rootDir, lockPath)}`);
  }

  try {
    return fn();
  } finally {
    try {
      fs.unlinkSync(lockPath);
    } catch {
      // Ignore missing lock cleanup on fast races.
    }
  }
}

export function loadRun(rootDir, runId) {
  return readJson(runFilePath(rootDir, runId));
}

export function saveRun(rootDir, run) {
  writeJson(runFilePath(rootDir, run.runId), run);
}

export function setActiveRun(rootDir, runId, branch = currentBranch(rootDir)) {
  writeJson(activeRunFilePath(rootDir, branch), { branch, runId });
}

export function resolveActiveRunId(rootDir, explicitRunId = '') {
  if (explicitRunId) return explicitRunId;
  const pointerPath = activeRunFilePath(rootDir);
  const pointer = readJson(pointerPath);
  return String(pointer.runId ?? '').trim();
}

export function clearActiveRun(rootDir, runId = '', branch = currentBranch(rootDir)) {
  const pointerPath = activeRunFilePath(rootDir, branch);
  if (!fs.existsSync(pointerPath)) return;
  const pointer = readJson(pointerPath);
  if (!runId || pointer.runId === runId) {
    fs.unlinkSync(pointerPath);
  }
}

export function appendEvent(rootDir, runId, event) {
  const filePath = eventFilePath(rootDir, runId);
  ensureDir(path.dirname(filePath));
  fs.appendFileSync(filePath, `${JSON.stringify(event)}\n`);
}

export function readEvents(rootDir, runId) {
  const filePath = eventFilePath(rootDir, runId);
  if (!fs.existsSync(filePath)) return [];
  return fs.readFileSync(filePath, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export function listRuns(rootDir) {
  const { telemetry } = telemetryConfig(rootDir);
  const dirPath = path.join(rootDir, telemetry.runsDir);
  if (!fs.existsSync(dirPath)) return [];
  return fs.readdirSync(dirPath)
    .filter((entry) => entry.endsWith('.json'))
    .sort((left, right) => left.localeCompare(right))
    .map((entry) => readJson(path.join(dirPath, entry)))
    .filter((run) => run.runId);
}

export function agentManifest(rootDir, agentId) {
  return loadAgentManifests(rootDir).find((item) => item.id === agentId) ?? null;
}

export function runMetrics(run, events) {
  const ordered = [...events].sort((left, right) => String(left.timestamp).localeCompare(String(right.timestamp)));
  const firstEdit = ordered.find((event) => event.type === 'first_edit');
  const beforeFirstEdit = firstEdit
    ? ordered.filter((event) => String(event.timestamp).localeCompare(String(firstEdit.timestamp)) <= 0)
    : ordered;
  const docsBeforeFirstEdit = beforeFirstEdit.filter((event) => event.type === 'doc_open').length;
  const retrievalBeforeFirstEdit = beforeFirstEdit.filter((event) => event.type === 'retrieve_query').length;
  const registryBeforeFirstEdit = beforeFirstEdit.filter((event) => event.type === 'registry_query').length;
  const startedAt = run.startedAt ? Date.parse(run.startedAt) : NaN;
  const endedAt = run.endedAt ? Date.parse(run.endedAt) : NaN;
  const derivedActualMinutes = Number.isFinite(startedAt) && Number.isFinite(endedAt)
    ? Number(((endedAt - startedAt) / 60000).toFixed(2))
    : null;
  const explicitActual = run.actualMinutes;
  const actualMinutes = explicitActual === '' || explicitActual === null || typeof explicitActual === 'undefined'
    ? derivedActualMinutes
    : (Number.isFinite(Number(explicitActual)) ? Number(explicitActual) : derivedActualMinutes);
  const explicitBaseline = run.baselineMinutes;
  const baselineMinutes = explicitBaseline === '' || explicitBaseline === null || typeof explicitBaseline === 'undefined'
    ? null
    : (Number.isFinite(Number(explicitBaseline)) ? Number(explicitBaseline) : null);
  const timeSavedMinutes = baselineMinutes !== null && actualMinutes !== null
    ? Number((baselineMinutes - actualMinutes).toFixed(2))
    : null;
  return {
    docsBeforeFirstEdit,
    retrievalBeforeFirstEdit,
    registryBeforeFirstEdit,
    actualMinutes,
    baselineMinutes,
    timeSavedMinutes,
  };
}

export function autoTelemetryEvent(rootDir, type, payload = {}) {
  const { telemetry } = telemetryConfig(rootDir);
  if (!telemetry.enabled) return null;
  const runId = resolveActiveRunId(rootDir);
  if (!runId) return null;
  const event = {
    runId,
    type,
    timestamp: new Date().toISOString(),
    ...payload,
  };
  withTelemetryLock(rootDir, () => {
    appendEvent(rootDir, runId, event);
  });
  return event;
}
