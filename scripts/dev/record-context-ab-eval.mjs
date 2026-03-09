#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function git(args, cwd) {
  return spawnSync('git', args, { cwd, encoding: 'utf8', stdio: 'pipe' });
}

function sanitize(value) {
  return String(value).trim().replace(/[^a-zA-Z0-9._-]+/g, '-');
}

function parseBoolean(value, flag) {
  if (value === 'true' || value === 'yes') return true;
  if (value === 'false' || value === 'no') return false;
  throw new Error(`[eval:ab:record] ${flag} must be true/false or yes/no`);
}

const rootDir = git(['rev-parse', '--show-toplevel'], process.cwd()).stdout.trim();
const taskDir = path.join(rootDir, '.agent-context/evaluations/tasks');
fs.mkdirSync(taskDir, { recursive: true });

const options = {
  taskId: '',
  surface: '',
  label: '',
  notes: '',
  routedDocs: null,
  baselineDocs: null,
  routedMinutes: null,
  baselineMinutes: null,
  routedSuccess: 'pass',
  baselineSuccess: 'pass',
  routedArchiveUsed: false,
  baselineArchiveUsed: false,
  routedPrecision: null,
  baselinePrecision: null,
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  const next = process.argv[index + 1];
  if (current === '--task-id') { options.taskId = next ?? ''; index += 1; continue; }
  if (current === '--surface') { options.surface = next ?? ''; index += 1; continue; }
  if (current === '--label') { options.label = next ?? ''; index += 1; continue; }
  if (current === '--notes') { options.notes = next ?? ''; index += 1; continue; }
  if (current === '--routed-docs') { options.routedDocs = Number(next); index += 1; continue; }
  if (current === '--baseline-docs') { options.baselineDocs = Number(next); index += 1; continue; }
  if (current === '--routed-minutes') { options.routedMinutes = Number(next); index += 1; continue; }
  if (current === '--baseline-minutes') { options.baselineMinutes = Number(next); index += 1; continue; }
  if (current === '--routed-success') { options.routedSuccess = next ?? ''; index += 1; continue; }
  if (current === '--baseline-success') { options.baselineSuccess = next ?? ''; index += 1; continue; }
  if (current === '--routed-archive-used') { options.routedArchiveUsed = parseBoolean(next ?? '', current); index += 1; continue; }
  if (current === '--baseline-archive-used') { options.baselineArchiveUsed = parseBoolean(next ?? '', current); index += 1; continue; }
  if (current === '--routed-precision') { options.routedPrecision = Number(next); index += 1; continue; }
  if (current === '--baseline-precision') { options.baselinePrecision = Number(next); index += 1; continue; }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/record-context-ab-eval.mjs --task-id <id> --surface <surface> --routed-docs <n> --baseline-docs <n> --routed-minutes <n> --baseline-minutes <n> [--routed-success pass|fail] [--baseline-success pass|fail] [--routed-archive-used yes|no] [--baseline-archive-used yes|no] [--label <text>] [--notes <text>]');
    process.exit(0);
  }
  throw new Error(`[eval:ab:record] unknown option: ${current}`);
}

if (!options.taskId || !options.surface) {
  throw new Error('[eval:ab:record] --task-id and --surface are required');
}

for (const [label, value] of [
  ['--routed-docs', options.routedDocs],
  ['--baseline-docs', options.baselineDocs],
  ['--routed-minutes', options.routedMinutes],
  ['--baseline-minutes', options.baselineMinutes],
]) {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`[eval:ab:record] ${label} must be a non-negative number`);
  }
}

const passFail = new Set(['pass', 'fail']);
if (!passFail.has(options.routedSuccess) || !passFail.has(options.baselineSuccess)) {
  throw new Error('[eval:ab:record] success flags must be pass or fail');
}

const docDelta = options.baselineDocs - options.routedDocs;
const latencyDeltaMinutes = options.baselineMinutes - options.routedMinutes;
const precisionDelta = Number.isFinite(options.routedPrecision) && Number.isFinite(options.baselinePrecision)
  ? options.routedPrecision - options.baselinePrecision
  : null;
const archiveAvoided = options.baselineArchiveUsed && !options.routedArchiveUsed;
const routedWin = (
  (options.routedSuccess === 'pass' || options.baselineSuccess === 'fail') &&
  (docDelta > 0 || latencyDeltaMinutes > 0 || archiveAvoided || (precisionDelta !== null && precisionDelta > 0))
);

const result = {
  version: 1,
  recordedAt: new Date().toISOString(),
  taskId: options.taskId,
  surface: options.surface,
  label: options.label || options.taskId,
  notes: options.notes,
  git: {
    branch: git(['branch', '--show-current'], rootDir).stdout.trim() || 'HEAD',
    head: git(['rev-parse', 'HEAD'], rootDir).stdout.trim() || null,
  },
  routed: {
    docsOpenedBeforeFirstEdit: options.routedDocs,
    minutesToFirstCorrectEdit: options.routedMinutes,
    success: options.routedSuccess,
    archiveUsed: options.routedArchiveUsed,
    retrievalPrecision: Number.isFinite(options.routedPrecision) ? options.routedPrecision : null,
  },
  baseline: {
    docsOpenedBeforeFirstEdit: options.baselineDocs,
    minutesToFirstCorrectEdit: options.baselineMinutes,
    success: options.baselineSuccess,
    archiveUsed: options.baselineArchiveUsed,
    retrievalPrecision: Number.isFinite(options.baselinePrecision) ? options.baselinePrecision : null,
  },
  deltas: {
    docReduction: docDelta,
    latencyReductionMinutes: latencyDeltaMinutes,
    retrievalPrecisionDelta: precisionDelta,
    archiveAvoided,
  },
  routedWin,
};

const outputPath = path.join(taskDir, `${sanitize(options.taskId)}.json`);
fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`);
console.log(`[eval:ab:record] wrote ${path.relative(rootDir, outputPath)}`);
