#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const configPath = path.join(rootDir, 'context-kit.json');
const outputPath = path.join(rootDir, 'docs/generated/context-ab-report.md');
const evalDir = path.join(rootDir, '.agent-context/evaluations/tasks');
const checkMode = process.argv.includes('--check');

function readJson(filePath) {
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
}

function average(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function formatNumber(value) {
  return value === null ? 'n/a' : `${value.toFixed(2)}`;
}

function listRecords() {
  if (!fs.existsSync(evalDir)) return [];
  return fs.readdirSync(evalDir)
    .filter((name) => name.endsWith('.json'))
    .map((name) => readJson(path.join(evalDir, name)))
    .filter((item) => item && item.taskId)
    .sort((left, right) => String(left.recordedAt ?? '').localeCompare(String(right.recordedAt ?? '')));
}

const config = readJson(configPath);
const targets = {
  minComparisons: Number(config.evaluation?.ab?.minComparisons ?? 1),
  targetDocsBeforeFirstEdit: Number(config.evaluation?.ab?.targetDocsBeforeFirstEdit ?? 6),
  targetResumeLatencyMinutes: Number(config.evaluation?.ab?.targetResumeLatencyMinutes ?? 3),
};

const records = listRecords();
const docDeltas = records.map((item) => Number(item.deltas?.docReduction)).filter(Number.isFinite);
const latencyDeltas = records.map((item) => Number(item.deltas?.latencyReductionMinutes)).filter(Number.isFinite);
const precisionDeltas = records.map((item) => Number(item.deltas?.retrievalPrecisionDelta)).filter(Number.isFinite);
const routedWins = records.filter((item) => item.routedWin).length;
const archiveAvoided = records.filter((item) => item.deltas?.archiveAvoided).length;
const acceptanceReady = records.length >= targets.minComparisons && routedWins >= 1;

const content = [
  '# Context A/B Report',
  '',
  'This report summarizes routed-vs-baseline task comparisons recorded with `npm run eval:ab:record`.',
  '',
  '## Summary',
  '',
  `- Comparisons recorded: \`${records.length}\``,
  `- Routed wins: \`${routedWins}\``,
  `- Average docs reduction: \`${formatNumber(average(docDeltas))}\``,
  `- Average latency reduction (minutes): \`${formatNumber(average(latencyDeltas))}\``,
  `- Average retrieval precision delta: \`${formatNumber(average(precisionDeltas))}\``,
  `- Archive avoided count: \`${archiveAvoided}\``,
  '',
  '## Acceptance Gate',
  '',
  `- ${acceptanceReady ? 'PASS' : 'FAIL'}: recorded comparisons >= \`${targets.minComparisons}\` and routed mode wins at least once`,
  '',
  '## Targets',
  '',
  `- Docs before first edit target: \`<= ${targets.targetDocsBeforeFirstEdit}\``,
  `- Resume latency target: \`< ${targets.targetResumeLatencyMinutes} min\``,
  '',
  '## Comparisons',
  '',
  '| Task ID | Surface | Routed Docs | Baseline Docs | Routed Minutes | Baseline Minutes | Routed Success | Baseline Success | Routed Win |',
  '| --- | --- | --- | --- | --- | --- | --- | --- | --- |',
  ...(records.length
    ? records.map((item) => `| \`${item.taskId}\` | \`${item.surface}\` | ${item.routed?.docsOpenedBeforeFirstEdit ?? 'n/a'} | ${item.baseline?.docsOpenedBeforeFirstEdit ?? 'n/a'} | ${item.routed?.minutesToFirstCorrectEdit ?? 'n/a'} | ${item.baseline?.minutesToFirstCorrectEdit ?? 'n/a'} | \`${item.routed?.success ?? 'n/a'}\` | \`${item.baseline?.success ?? 'n/a'}\` | \`${item.routedWin ? 'yes' : 'no'}\` |`)
    : ['| none | none | n/a | n/a | n/a | n/a | n/a | n/a | n/a |']),
  '',
  '## How To Use',
  '',
  '- Record one comparison per representative task.',
  '- Keep the repo commit, machine envelope, and prompt scaffolding constant across routed and baseline modes.',
  '- Use this report with `docs/generated/context-efficiency-report.md` and the runtime benchmark before calling the context design final.',
  '',
].join('\n') + '\n';

if (checkMode) {
  const existing = fs.existsSync(outputPath) ? fs.readFileSync(outputPath, 'utf8') : null;
  if (existing !== content) {
    throw new Error('[context-ab] stale generated file: docs/generated/context-ab-report.md');
  }
} else {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, content);
}
