#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { listRuns, readEvents, runMetrics, telemetryConfig, withTelemetryLock } from './agent-telemetry-lib.mjs';

const rootDir = process.cwd();
const checkMode = process.argv.includes('--check');
const { telemetry } = telemetryConfig(rootDir);
const outputJsonPath = path.join(rootDir, telemetry.reportPath ?? 'docs/generated/agent-usage-report.json');
const outputMarkdownPath = path.join(rootDir, 'docs/generated/agent-usage-report.md');
function average(values) {
  if (values.length === 0) return null;
  return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2));
}

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[agent-usage] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

function groupByPrimitive(runs, key) {
  const buckets = new Map();
  for (const run of runs) {
    const bucketKey = String(run.primitives?.[key] ?? 'unspecified');
    const bucket = buckets.get(bucketKey) ?? [];
    bucket.push(run);
    buckets.set(bucketKey, bucket);
  }
  return Array.from(buckets.entries())
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([value, bucketRuns]) => ({
      value,
      runCount: bucketRuns.length,
      finishedRunCount: bucketRuns.filter((run) => run.status !== 'in_progress').length,
      averageActualMinutes: average(bucketRuns.map((run) => run.metrics.actualMinutes).filter((item) => item !== null)),
      averageBaselineMinutes: average(bucketRuns.map((run) => run.metrics.baselineMinutes).filter((item) => item !== null)),
      totalEstimatedTimeSavedMinutes: (() => {
        const values = bucketRuns.map((run) => run.metrics.timeSavedMinutes).filter((item) => item !== null);
        return values.length ? Number(values.reduce((sum, item) => sum + item, 0).toFixed(2)) : null;
      })(),
    }));
}

withTelemetryLock(rootDir, () => {
  const runs = listRuns(rootDir)
    .map((run) => {
      const metrics = runMetrics(run, readEvents(rootDir, run.runId));
      return { ...run, metrics };
    })
    .sort((left, right) => String(right.startedAt ?? '').localeCompare(String(left.startedAt ?? '')));

  const finishedRuns = runs.filter((run) => run.status !== 'in_progress');
  const successRuns = finishedRuns.filter((run) => run.status === 'success');
  const actualMinutes = finishedRuns.map((run) => run.metrics.actualMinutes).filter((value) => value !== null);
  const baselineMinutes = finishedRuns.map((run) => run.metrics.baselineMinutes).filter((value) => value !== null);
  const timeSavedMinutes = finishedRuns.map((run) => run.metrics.timeSavedMinutes).filter((value) => value !== null);
  const docsBeforeFirstEdit = runs.map((run) => run.metrics.docsBeforeFirstEdit);
  const retrievalBeforeFirstEdit = runs.map((run) => run.metrics.retrievalBeforeFirstEdit);
  const registryBeforeFirstEdit = runs.map((run) => run.metrics.registryBeforeFirstEdit);

  const summary = {
    version: 1,
    runCount: runs.length,
    finishedRunCount: finishedRuns.length,
    successRatePct: finishedRuns.length ? Number(((successRuns.length / finishedRuns.length) * 100).toFixed(1)) : null,
    averageActualMinutes: average(actualMinutes),
    averageBaselineMinutes: average(baselineMinutes),
    totalEstimatedTimeSavedMinutes: timeSavedMinutes.length ? Number(timeSavedMinutes.reduce((sum, value) => sum + value, 0).toFixed(2)) : null,
    averageDocsBeforeFirstEdit: average(docsBeforeFirstEdit),
    averageRetrievalQueriesBeforeFirstEdit: average(retrievalBeforeFirstEdit),
    averageRegistryQueriesBeforeFirstEdit: average(registryBeforeFirstEdit),
    primitiveBreakdowns: {
      purpose: groupByPrimitive(runs, 'purpose'),
      autonomy: groupByPrimitive(runs, 'autonomy'),
      taskComplexity: groupByPrimitive(runs, 'taskComplexity'),
    },
    runs: runs.map((run) => ({
      runId: run.runId,
      agent: run.agent,
      role: run.role,
      surface: run.surface,
      branch: run.branch,
      status: run.status,
      primitives: run.primitives,
      summary: run.summary,
      startedAt: run.startedAt,
      endedAt: run.endedAt,
      metrics: run.metrics,
    })),
  };

  const primitiveRows = Object.entries(summary.primitiveBreakdowns)
    .flatMap(([label, buckets]) => buckets.map((bucket) => `| \`${label}\` | \`${bucket.value}\` | \`${bucket.runCount}\` | ${bucket.averageActualMinutes ?? 'n/a'} | ${bucket.totalEstimatedTimeSavedMinutes ?? 'n/a'} |`));

  const markdown = [
    '# Agent Usage Report',
    '',
    'This generated report summarizes runtime evidence for agent usage, context efficiency, and estimated time saved.',
    '',
    '## Summary',
    '',
    `- Runs recorded: \`${summary.runCount}\``,
    `- Finished runs: \`${summary.finishedRunCount}\``,
    `- Success rate: \`${summary.successRatePct === null ? 'n/a' : `${summary.successRatePct}%`}\``,
    `- Avg actual minutes: \`${summary.averageActualMinutes ?? 'n/a'}\``,
    `- Avg baseline minutes: \`${summary.averageBaselineMinutes ?? 'n/a'}\``,
    `- Total estimated time saved (minutes): \`${summary.totalEstimatedTimeSavedMinutes ?? 'n/a'}\``,
    `- Avg docs before first edit: \`${summary.averageDocsBeforeFirstEdit ?? 'n/a'}\``,
    `- Avg retrieval queries before first edit: \`${summary.averageRetrievalQueriesBeforeFirstEdit ?? 'n/a'}\``,
    `- Avg registry queries before first edit: \`${summary.averageRegistryQueriesBeforeFirstEdit ?? 'n/a'}\``,
    '',
    '## Economic Primitive Breakdown',
    '',
    '| Primitive | Value | Runs | Avg Actual Minutes | Total Estimated Time Saved |',
    '| --- | --- | --- | --- | --- |',
    ...(primitiveRows.length ? primitiveRows : ['| none | none | 0 | n/a | n/a |']),
    '',
    '## Recent Runs',
    '',
    '| Run | Agent | Surface | Status | Actual Minutes | Baseline Minutes | Time Saved |',
    '| --- | --- | --- | --- | --- | --- | --- |',
    ...(summary.runs.length
      ? summary.runs.slice(0, 20).map((run) => `| \`${run.runId}\` | \`${run.agent}\` | \`${run.surface}\` | \`${run.status}\` | ${run.metrics.actualMinutes ?? 'n/a'} | ${run.metrics.baselineMinutes ?? 'n/a'} | ${run.metrics.timeSavedMinutes ?? 'n/a'} |`)
      : ['| none | none | none | none | n/a | n/a | n/a |']),
    '',
    '## How To Use',
    '',
    '- Start a measured run with `npm run agent:start -- --agent "<agent-id>" --surface "<surface>"`.',
    '- Record meaningful events with `npm run agent:event -- --type doc_open --path "<repo-path>"`.',
    '- Finish the run with `npm run agent:finish -- --status success --baseline-minutes <n>`.',
    '- Refresh this report with `npm run agent:report`.',
    '',
  ].join('\n') + '\n';

  writeManaged(outputJsonPath, `${JSON.stringify(summary, null, 2)}\n`);
  writeManaged(outputMarkdownPath, markdown);
});
