#!/usr/bin/env node
import { appendEvent, resolveActiveRunId, withTelemetryLock } from './agent-telemetry-lib.mjs';

const rootDir = process.cwd();
const options = {
  runId: '',
  type: '',
  path: '',
  note: '',
  value: '',
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--run-id') {
    options.runId = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--type') {
    options.type = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--path') {
    options.path = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--note') {
    options.note = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--value') {
    options.value = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/log-agent-event.mjs --type <event-type> [--run-id <id>] [--path <repo-path>] [--note <text>] [--value <value>]');
    process.exit(0);
  }
  throw new Error(`[agent:event] unknown option: ${current}`);
}

if (!options.type) {
  throw new Error('[agent:event] missing required flag: --type');
}

const runId = resolveActiveRunId(rootDir, options.runId);
if (!runId) {
  throw new Error('[agent:event] no active run found for this branch');
}

withTelemetryLock(rootDir, () => {
  appendEvent(rootDir, runId, {
    runId,
    type: options.type,
    path: options.path,
    note: options.note,
    value: options.value,
    timestamp: new Date().toISOString(),
  });
});
console.log(`[agent:event] appended ${options.type} to ${runId}`);
