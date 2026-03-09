#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd,
    encoding: 'utf8',
    env: options.env ?? process.env,
    stdio: options.stdio ?? 'pipe',
  });
}

function mustRun(command, args, options = {}) {
  const result = run(command, args, options);
  if (result.status !== 0) {
    const rendered = [command, ...args].join(' ');
    throw new Error(`[context-benchmark] command failed: ${rendered}\n${result.stderr ?? ''}`);
  }
  return result;
}

function parseArgs(argv) {
  const options = {
    baseUrl: 'http://localhost:4173',
    runs: null,
    warmupRuns: null,
    mode: null,
    browserBin: '',
    pages: [],
    apis: [],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === '--base-url') {
      options.baseUrl = argv[index + 1] ?? options.baseUrl;
      index += 1;
      continue;
    }
    if (current === '--runs') {
      options.runs = Number(argv[index + 1] ?? options.runs);
      index += 1;
      continue;
    }
    if (current === '--warmup') {
      options.warmupRuns = Number(argv[index + 1] ?? options.warmupRuns);
      index += 1;
      continue;
    }
    if (current === '--mode') {
      options.mode = argv[index + 1] ?? options.mode;
      index += 1;
      continue;
    }
    if (current === '--browser-bin') {
      options.browserBin = argv[index + 1] ?? '';
      index += 1;
      continue;
    }
    if (current === '--page') {
      options.pages.push(argv[index + 1] ?? '');
      index += 1;
      continue;
    }
    if (current === '--api') {
      options.apis.push(argv[index + 1] ?? '');
      index += 1;
      continue;
    }
    if (current === '-h' || current === '--help') {
      printUsage();
      process.exit(0);
    }
    throw new Error(`[context-benchmark] unknown option: ${current}`);
  }

  return options;
}

function printUsage() {
  console.log('Usage: node scripts/dev/run-context-benchmark.mjs [--base-url <url>] [--runs <count>] [--warmup <count>] [--mode <smoke|browser|all>] [--browser-bin <path>] [--page <route>] [--api <route:statuses>]');
}

function readJson(filePath) {
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
}

function mean(values) {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function stddev(values) {
  if (values.length < 2) return null;
  const avg = mean(values);
  const variance = values.reduce((sum, value) => sum + ((value - avg) ** 2), 0) / values.length;
  return Math.sqrt(variance);
}

function formatMs(value) {
  return value === null ? 'n/a' : `${Math.round(value)} ms`;
}

function formatPct(value) {
  return value === null ? 'n/a' : `${value.toFixed(1)}%`;
}

function safeReadVersion(command, args) {
  const result = run(command, args);
  if (result.status !== 0) return null;
  return (result.stdout || result.stderr || '').trim() || null;
}

function git(commandArgs, rootDir) {
  return run('git', commandArgs, { cwd: rootDir });
}

function detectProbeRoute(config) {
  const firstPage = config.harness?.pages?.[0];
  return typeof firstPage === 'string' && firstPage ? firstPage : '/';
}

function probe(baseUrl, route) {
  const target = `${baseUrl.replace(/\/$/, '')}${route}`;
  const result = run('curl', ['-sS', '-L', '-o', '/dev/null', '-w', '%{http_code}', target]);
  if (result.status !== 0) {
    return { ok: false, status: 'curl-error' };
  }
  const status = `${result.stdout || ''}`.trim();
  return { ok: status.startsWith('2') || status.startsWith('3'), status };
}

function buildLoopbackCandidates(baseUrl) {
  let parsed;
  try {
    parsed = new URL(baseUrl);
  } catch {
    return [baseUrl];
  }

  const host = parsed.hostname;
  const isLoopback = ['127.0.0.1', 'localhost', '::1', '[::1]'].includes(host);
  if (!isLoopback) return [baseUrl];

  const hosts = ['localhost', '127.0.0.1', '::1'];
  const candidates = [];
  for (const nextHost of hosts) {
    const candidate = new URL(parsed.toString());
    candidate.hostname = nextHost;
    candidates.push(candidate.toString().replace(/\/$/, ''));
  }
  return [...new Set([baseUrl.replace(/\/$/, ''), ...candidates])];
}

function resolveBaseUrl(baseUrl, route) {
  const candidates = buildLoopbackCandidates(baseUrl);
  for (const candidate of candidates) {
    const result = probe(candidate, route);
    if (result.ok) {
      return { effectiveBaseUrl: candidate, probeStatus: result.status };
    }
  }
  return { effectiveBaseUrl: baseUrl.replace(/\/$/, ''), probeStatus: 'unreachable' };
}

function runStep(rootDir, mode, options, runId, logDir) {
  const stepLogBase = path.join(logDir, `${runId}-${mode}`);
  const commandArgs = mode === 'smoke'
    ? ['scripts/dev/run-context-harness.sh', '--run-id', runId, '--base-url', options.baseUrl]
    : ['scripts/dev/run-browser-context-harness.sh', '--run-id', runId, '--base-url', options.baseUrl];

  for (const page of options.pages) {
    if (page) commandArgs.push('--page', page);
  }

  if (mode === 'smoke') {
    for (const api of options.apis) {
      if (api) commandArgs.push('--api', api);
    }
  } else if (options.browserBin) {
    commandArgs.push('--browser-bin', options.browserBin);
  }

  const result = run('bash', commandArgs, { cwd: rootDir });
  fs.writeFileSync(`${stepLogBase}.stdout.log`, result.stdout ?? '');
  fs.writeFileSync(`${stepLogBase}.stderr.log`, result.stderr ?? '');
  return result;
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

const repoRoot = mustRun('git', ['rev-parse', '--show-toplevel']).stdout.trim();
const cliOptions = parseArgs(process.argv.slice(2));
const config = readJson(path.join(repoRoot, 'context-kit.json'));
const benchmarkDefaults = config.evaluation?.benchmark ?? {};
const targetDefaults = config.evaluation?.targets ?? {};
const options = {
  baseUrl: cliOptions.baseUrl,
  runs: Number.isFinite(cliOptions.runs) ? cliOptions.runs : Number(benchmarkDefaults.runs ?? 3),
  warmupRuns: Number.isFinite(cliOptions.warmupRuns) ? cliOptions.warmupRuns : Number(benchmarkDefaults.warmupRuns ?? 1),
  mode: cliOptions.mode ?? benchmarkDefaults.mode ?? 'smoke',
  browserBin: cliOptions.browserBin || '',
  pages: cliOptions.pages,
  apis: cliOptions.apis,
};

if (!['smoke', 'browser', 'all'].includes(options.mode)) {
  throw new Error(`[context-benchmark] unsupported mode: ${options.mode}`);
}
if (!Number.isInteger(options.runs) || options.runs < 2) {
  throw new Error('[context-benchmark] --runs must be an integer >= 2 so duration variance can be measured');
}
if (!Number.isInteger(options.warmupRuns) || options.warmupRuns < 0) {
  throw new Error('[context-benchmark] --warmup must be a non-negative integer');
}

const runId = `${new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '-')}-context-benchmark`;
const artifactDir = path.join(repoRoot, '.agent-context/evaluations', runId);
const runLogsDir = path.join(artifactDir, 'run-logs');
fs.mkdirSync(runLogsDir, { recursive: true });
const probeRoute = detectProbeRoute(config);
const baseUrlResolution = resolveBaseUrl(options.baseUrl, probeRoute);
options.baseUrl = baseUrlResolution.effectiveBaseUrl;

const prep = run('npm', ['run', 'docs:refresh'], { cwd: repoRoot });
fs.writeFileSync(path.join(artifactDir, 'docs-refresh.stdout.log'), prep.stdout ?? '');
fs.writeFileSync(path.join(artifactDir, 'docs-refresh.stderr.log'), prep.stderr ?? '');
if (prep.status !== 0) {
  throw new Error('[context-benchmark] docs:refresh failed before benchmark');
}

const contextReportPath = path.join(repoRoot, 'docs/generated/context-efficiency-report.md');
if (fs.existsSync(contextReportPath)) {
  fs.copyFileSync(contextReportPath, path.join(artifactDir, 'context-efficiency-report.snapshot.md'));
}

const gitStatus = git(['status', '--short'], repoRoot);
const environment = {
  timestamp: new Date().toISOString(),
  requestedBaseUrl: cliOptions.baseUrl,
  effectiveBaseUrl: options.baseUrl,
  mode: options.mode,
  runs: options.runs,
  warmupRuns: options.warmupRuns,
  probeRoute,
  initialProbeStatus: baseUrlResolution.probeStatus,
  platform: os.platform(),
  release: os.release(),
  arch: os.arch(),
  cpus: typeof os.availableParallelism === 'function' ? os.availableParallelism() : os.cpus().length,
  totalMemoryBytes: os.totalmem(),
  node: process.version,
  npm: safeReadVersion('npm', ['--version']),
  python3: safeReadVersion('python3', ['--version']),
  browserBin: options.browserBin || null,
  git: {
    branch: git(['branch', '--show-current'], repoRoot).stdout.trim(),
    commit: git(['rev-parse', 'HEAD'], repoRoot).stdout.trim(),
    dirty: Boolean((gitStatus.stdout || '').trim()),
  },
  thresholds: {
    noiseRateMaxPct: Number(targetDefaults.noiseRateMaxPct ?? 10),
    durationCvMaxPct: Number(benchmarkDefaults.maxDurationCvPct ?? 15),
  },
};
writeJson(path.join(artifactDir, 'environment.json'), environment);

const totalRuns = options.warmupRuns + options.runs;
const results = [];

for (let index = 0; index < totalRuns; index += 1) {
  const measured = index >= options.warmupRuns;
  const phase = measured ? 'measured' : 'warmup';
  const runNumber = String(index + 1).padStart(2, '0');
  const subRunId = `${runId}-${phase}-${runNumber}`;
  const beforeProbe = probe(options.baseUrl, environment.probeRoute);
  const startedAt = Date.now();
  let commandStatus = 0;
  let classification = 'pass';
  let step = options.mode;

  if (!beforeProbe.ok) {
    commandStatus = 1;
    classification = 'infra_candidate';
  } else if (options.mode === 'all') {
    const smokeResult = runStep(repoRoot, 'smoke', options, subRunId, runLogsDir);
    if (smokeResult.status !== 0) {
      commandStatus = smokeResult.status ?? 1;
      step = 'smoke';
    } else {
      const browserResult = runStep(repoRoot, 'browser', options, subRunId, runLogsDir);
      if (browserResult.status !== 0) {
        commandStatus = browserResult.status ?? 1;
        step = 'browser';
      }
    }
  } else {
    const result = runStep(repoRoot, options.mode, options, subRunId, runLogsDir);
    if (result.status !== 0) {
      commandStatus = result.status ?? 1;
    }
  }

  const durationMs = Date.now() - startedAt;
  const afterProbe = probe(options.baseUrl, environment.probeRoute);
  if (commandStatus !== 0 && classification !== 'infra_candidate') {
    classification = afterProbe.ok ? 'harness_or_product_failure' : 'infra_candidate';
  }

  results.push({
    runId: subRunId,
    index: index + 1,
    phase,
    mode: step,
    status: commandStatus === 0 ? 'pass' : 'fail',
    classification,
    durationMs,
    probeBefore: beforeProbe.status,
    probeAfter: afterProbe.status,
    artifactRef: `.agent-context/harness/${subRunId}`,
  });
}

const measuredResults = results.filter((item) => item.phase === 'measured');
const measuredPasses = measuredResults.filter((item) => item.status === 'pass');
const measuredDurations = measuredPasses.map((item) => item.durationMs);
const infraNoiseRatePct = measuredResults.length
  ? (measuredResults.filter((item) => item.classification === 'infra_candidate').length / measuredResults.length) * 100
  : null;
const passRatePct = measuredResults.length
  ? (measuredPasses.length / measuredResults.length) * 100
  : null;
const durationMeanMs = mean(measuredDurations);
const durationStddevMs = stddev(measuredDurations);
const durationCvPct = durationMeanMs && durationStddevMs !== null
  ? (durationStddevMs / durationMeanMs) * 100
  : null;
const benchmarkGate = Boolean(
  measuredResults.length >= options.runs &&
  passRatePct === 100 &&
  infraNoiseRatePct !== null &&
  infraNoiseRatePct <= environment.thresholds.noiseRateMaxPct &&
  durationCvPct !== null &&
  durationCvPct <= environment.thresholds.durationCvMaxPct,
);

const runsTsvPath = path.join(artifactDir, 'runs.tsv');
const tsvLines = [
  'run_id\tphase\tmode\tstatus\tclassification\tduration_ms\tprobe_before\tprobe_after\tartifact_ref',
  ...results.map((item) => [
    item.runId,
    item.phase,
    item.mode,
    item.status,
    item.classification,
    item.durationMs,
    item.probeBefore,
    item.probeAfter,
    item.artifactRef,
  ].join('\t')),
];
fs.writeFileSync(runsTsvPath, `${tsvLines.join('\n')}\n`);

const metrics = {
  measuredRuns: measuredResults.length,
  measuredPasses: measuredPasses.length,
  passRatePct,
  infraNoiseRatePct,
  durationMeanMs,
  durationStddevMs,
  durationCvPct,
  benchmarkGate,
};
writeJson(path.join(artifactDir, 'metrics.json'), metrics);

const summaryLines = [
  '# Context Benchmark Summary',
  '',
  `- Run: \`${runId}\``,
  `- Base URL: \`${options.baseUrl}\``,
  `- Requested base URL: \`${environment.requestedBaseUrl}\``,
  `- Mode: \`${options.mode}\``,
  `- Warmup runs: \`${options.warmupRuns}\``,
  `- Measured runs: \`${options.runs}\``,
  `- Probe route: \`${environment.probeRoute}\``,
  '',
  '## Environment',
  '',
  `- Platform: \`${environment.platform} ${environment.release} (${environment.arch})\``,
  `- CPU parallelism: \`${environment.cpus}\``,
  `- Node: \`${environment.node}\``,
  `- npm: \`${environment.npm ?? 'n/a'}\``,
  `- Python: \`${environment.python3 ?? 'n/a'}\``,
  `- Git branch: \`${environment.git.branch}\``,
  `- Git commit: \`${environment.git.commit}\``,
  `- Git dirty: \`${environment.git.dirty ? 'yes' : 'no'}\``,
  '',
  '## Scorecard',
  '',
  `- Pass rate: \`${formatPct(passRatePct)}\``,
  `- Infra noise rate: \`${formatPct(infraNoiseRatePct)}\` (target: \`<= ${environment.thresholds.noiseRateMaxPct}%\`)`,
  `- Duration mean: \`${formatMs(durationMeanMs)}\``,
  `- Duration stddev: \`${formatMs(durationStddevMs)}\``,
  `- Duration CV: \`${formatPct(durationCvPct)}\` (target: \`<= ${environment.thresholds.durationCvMaxPct}%\`)`,
  `- Benchmark gate: \`${benchmarkGate ? 'PASS' : 'FAIL'}\``,
  '',
  '## Interpretation',
  '',
  '- Treat `infra_candidate` failures as environment noise until proven otherwise.',
  '- Treat `harness_or_product_failure` as a repo or harness issue to inspect locally.',
  '- Only compare context variants when the benchmark gate passes on the same machine envelope.',
  '',
  '## Artifacts',
  '',
  '- `environment.json`',
  '- `metrics.json`',
  '- `runs.tsv`',
  '- `run-logs/`',
  '- `context-efficiency-report.snapshot.md`',
  '',
];
fs.writeFileSync(path.join(artifactDir, 'summary.md'), `${summaryLines.join('\n')}\n`);

console.log(`[context-benchmark] wrote artifacts: ${path.relative(repoRoot, artifactDir)}`);
console.log(`[context-benchmark] benchmark gate: ${benchmarkGate ? 'PASS' : 'FAIL'}`);

if (!benchmarkGate) {
  process.exitCode = 1;
}
