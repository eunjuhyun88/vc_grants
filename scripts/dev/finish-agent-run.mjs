#!/usr/bin/env node
import { clearActiveRun, currentBranch, loadRun, resolveActiveRunId, saveRun, withTelemetryLock } from './agent-telemetry-lib.mjs';

const rootDir = process.cwd();
const options = {
  runId: '',
  status: 'success',
  summary: '',
  baselineMinutes: '',
  actualMinutes: '',
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--run-id') {
    options.runId = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--status') {
    options.status = process.argv[index + 1] ?? options.status;
    index += 1;
    continue;
  }
  if (current === '--summary') {
    options.summary = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--baseline-minutes') {
    options.baselineMinutes = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--actual-minutes') {
    options.actualMinutes = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/finish-agent-run.mjs [--run-id <id>] [--status success|blocked|abandoned] [--summary <text>] [--baseline-minutes <n>] [--actual-minutes <n>]');
    process.exit(0);
  }
  throw new Error(`[agent:finish] unknown option: ${current}`);
}

const runId = resolveActiveRunId(rootDir, options.runId);
if (!runId) {
  throw new Error('[agent:finish] no active run found for this branch');
}

let finalStatus = options.status;
withTelemetryLock(rootDir, () => {
  const run = loadRun(rootDir, runId);
  if (!run.runId) {
    throw new Error(`[agent:finish] run not found: ${runId}`);
  }

  run.status = options.status;
  finalStatus = run.status;
  run.summary = options.summary;
  run.endedAt = new Date().toISOString();
  run.baselineMinutes = options.baselineMinutes === '' ? run.baselineMinutes : Number(options.baselineMinutes);
  run.actualMinutes = options.actualMinutes === '' ? run.actualMinutes : Number(options.actualMinutes);

  saveRun(rootDir, run);
  clearActiveRun(rootDir, runId, run.branch || currentBranch(rootDir));
});
console.log(`[agent:finish] completed ${runId} with status=${finalStatus}`);
