#!/usr/bin/env node
import { agentManifest } from './agent-telemetry-lib.mjs';
import { currentBranch, saveRun, setActiveRun, telemetryConfig, withTelemetryLock } from './agent-telemetry-lib.mjs';

const rootDir = process.cwd();
const { telemetry } = telemetryConfig(rootDir);
const options = {
  runId: '',
  agent: '',
  surface: '',
  taskId: '',
  taskComplexity: telemetry.defaults.taskComplexity,
  skillLevel: telemetry.defaults.skillLevel,
  purpose: telemetry.defaults.purpose,
  autonomy: telemetry.defaults.autonomy,
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--run-id') {
    options.runId = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--agent') {
    options.agent = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--surface') {
    options.surface = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--task-id') {
    options.taskId = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--task-complexity') {
    options.taskComplexity = process.argv[index + 1] ?? options.taskComplexity;
    index += 1;
    continue;
  }
  if (current === '--skill-level') {
    options.skillLevel = process.argv[index + 1] ?? options.skillLevel;
    index += 1;
    continue;
  }
  if (current === '--purpose') {
    options.purpose = process.argv[index + 1] ?? options.purpose;
    index += 1;
    continue;
  }
  if (current === '--autonomy') {
    options.autonomy = process.argv[index + 1] ?? options.autonomy;
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/start-agent-run.mjs --agent <agent-id> [--surface <surface>] [--run-id <id>] [--task-id <id>] [--task-complexity <low|moderate|high>] [--skill-level <level>] [--purpose <purpose>] [--autonomy <guided|assisted|supervised|autonomous>]');
    process.exit(0);
  }
  throw new Error(`[agent:start] unknown option: ${current}`);
}

if (!options.agent) {
  throw new Error('[agent:start] missing required flag: --agent');
}

const manifest = agentManifest(rootDir, options.agent);
const runId = options.runId || `R-${new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)}-${options.agent}`;
const surface = options.surface || manifest?.surfaces?.[0] || '';
if (!surface) {
  throw new Error('[agent:start] missing surface and no manifest default found');
}

const run = {
  version: 1,
  runId,
  agent: options.agent,
  role: manifest?.role ?? '',
  branch: currentBranch(rootDir),
  surface,
  taskId: options.taskId,
  startedAt: new Date().toISOString(),
  endedAt: '',
  status: 'in_progress',
  summary: '',
  baselineMinutes: null,
  actualMinutes: null,
  primitives: {
    taskComplexity: options.taskComplexity,
    skillLevel: options.skillLevel,
    purpose: options.purpose,
    autonomy: options.autonomy,
  },
};

withTelemetryLock(rootDir, () => {
  saveRun(rootDir, run);
  setActiveRun(rootDir, runId, run.branch);
});
console.log(`[agent:start] run ${runId} active on ${run.branch}`);
