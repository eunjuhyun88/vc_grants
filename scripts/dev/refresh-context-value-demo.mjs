#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { readJson } from './context-registry-lib.mjs';

const rootDir = process.cwd();
const config = readJson(path.join(rootDir, 'context-kit.json'));
const checkMode = process.argv.includes('--check');
const outputJsonPath = path.join(rootDir, 'docs/generated/context-value-demo.json');
const outputMarkdownPath = path.join(rootDir, 'docs/generated/context-value-demo.md');
const excludedAllDocs = new Set([
  path.resolve(outputMarkdownPath),
  path.resolve(path.join(rootDir, 'docs/generated/context-efficiency-report.md')),
]);

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[context-value-demo] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

function listMarkdownFiles(dirPath) {
  if (!fs.existsSync(dirPath)) return [];
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...listMarkdownFiles(fullPath));
      continue;
    }
    if (entry.name.endsWith('.md')) files.push(fullPath);
  }
  return files;
}

function approxTokens(text) {
  return String(text).trim().split(/\s+/).filter(Boolean).length;
}

function bundleStats(files) {
  const existing = [...new Set(files)].filter((filePath) => fs.existsSync(filePath));
  const text = existing.map((filePath) => fs.readFileSync(filePath, 'utf8')).join('\n');
  const lines = existing.reduce((sum, filePath) => sum + fs.readFileSync(filePath, 'utf8').split('\n').length, 0);
  return {
    files: existing.length,
    lines,
    approxTokens: approxTokens(text),
  };
}

function reductionPct(smaller, larger) {
  if (!Number.isFinite(smaller) || !Number.isFinite(larger) || larger <= 0) return null;
  return Number((((larger - smaller) / larger) * 100).toFixed(1));
}

function formatNumber(value) {
  return value === null || typeof value === 'undefined' ? 'n/a' : String(value);
}

function loadAbRecords() {
  const evalDir = path.join(rootDir, '.agent-context/evaluations/tasks');
  if (!fs.existsSync(evalDir)) return [];
  return fs.readdirSync(evalDir)
    .filter((name) => name.endsWith('.json'))
    .map((name) => readJson(path.join(evalDir, name)))
    .filter((item) => item && item.taskId);
}

const smallMapFiles = [
  path.join(rootDir, 'README.md'),
  path.join(rootDir, 'AGENTS.md'),
  path.join(rootDir, 'docs/README.md'),
  path.join(rootDir, 'ARCHITECTURE.md'),
  path.join(rootDir, 'docs/SYSTEM_INTENT.md'),
  path.join(rootDir, 'docs/CONTEXT_ENGINEERING.md'),
  path.join(rootDir, 'docs/CLAUDE_COMPATIBILITY.md'),
  path.join(rootDir, 'docs/AGENT_FACTORY.md'),
  path.join(rootDir, 'docs/TOOL_DESIGN.md'),
  path.join(rootDir, 'docs/AGENT_OBSERVABILITY.md'),
];

const allDocsFiles = [
  path.join(rootDir, 'README.md'),
  path.join(rootDir, 'AGENTS.md'),
  path.join(rootDir, 'CLAUDE.md'),
  path.join(rootDir, 'ARCHITECTURE.md'),
  ...listMarkdownFiles(path.join(rootDir, '.claude')),
  ...listMarkdownFiles(path.join(rootDir, 'docs')),
  ...listMarkdownFiles(path.join(rootDir, 'agents')),
  ...listMarkdownFiles(path.join(rootDir, 'tools')),
].filter((filePath) => !excludedAllDocs.has(path.resolve(filePath)));

const smallMap = bundleStats(smallMapFiles);
const allDocs = bundleStats(allDocsFiles);
const smallMapReductionVsAllDocsPct = reductionPct(smallMap.approxTokens, allDocs.approxTokens);

const registryManifest = readJson(path.join(rootDir, config.registry?.manifestPath ?? 'docs/generated/context-registry.json'));
const retrievalIndex = readJson(path.join(rootDir, config.retrieval?.indexPath ?? 'docs/generated/contextual-retrieval-index.json'));
const agentCatalog = readJson(path.join(rootDir, config.agents?.catalogPath ?? 'docs/generated/agent-catalog.json'));
const toolCatalog = readJson(path.join(rootDir, config.tools?.catalogPath ?? 'docs/generated/tool-catalog.json'));
const agentUsage = readJson(path.join(rootDir, config.telemetry?.reportPath ?? 'docs/generated/agent-usage-report.json'));
const abRecords = loadAbRecords();

const latestRun = [...(agentUsage.runs ?? [])]
  .sort((left, right) => String(right.startedAt ?? '').localeCompare(String(left.startedAt ?? '')))[0] ?? null;

const feltChecks = [
  {
    label: 'Small start bundle',
    pass: smallMapReductionVsAllDocsPct !== null && smallMapReductionVsAllDocsPct >= Number(config.evaluation?.targets?.smallMapReductionVsAllDocsPct ?? 55),
    evidence: `${smallMap.approxTokens} tokens vs ${allDocs.approxTokens} tokens across all docs (${formatNumber(smallMapReductionVsAllDocsPct)}% smaller)`,
  },
  {
    label: 'Discovery works without chat memory',
    pass: (registryManifest.surfaces?.length ?? 0) > 0 && (agentCatalog.agentCount ?? 0) > 0 && (toolCatalog.toolCount ?? 0) > 0,
    evidence: `${registryManifest.surfaces?.length ?? 0} surfaces, ${agentCatalog.agentCount ?? 0} agents, ${toolCatalog.toolCount ?? 0} tools`,
  },
  {
    label: 'Ambiguity has a retrieval escape hatch',
    pass: Number(retrievalIndex.chunkCount ?? 0) > 0,
    evidence: `${retrievalIndex.chunkCount ?? 0} retrieval chunks across ${retrievalIndex.sourceCount ?? 0} sources`,
  },
  {
    label: 'Time-saved evidence exists',
    pass: Number(agentUsage.finishedRunCount ?? 0) > 0 && Number(agentUsage.totalEstimatedTimeSavedMinutes ?? 0) > 0,
    evidence: `${agentUsage.finishedRunCount ?? 0} finished runs, ${formatNumber(agentUsage.totalEstimatedTimeSavedMinutes ?? null)} minutes estimated saved`,
  },
  {
    label: 'Routed mode beat baseline at least once',
    pass: abRecords.length > 0 && abRecords.some((record) => record.routedWin),
    evidence: `${abRecords.filter((record) => record.routedWin).length}/${abRecords.length} routed wins`,
  },
];

const summary = {
  version: 1,
  smallMap,
  allDocs,
  smallMapReductionVsAllDocsPct,
  registry: {
    surfaceCount: registryManifest.surfaces?.length ?? 0,
    commandCount: registryManifest.commands?.length ?? 0,
  },
  agents: {
    count: agentCatalog.agentCount ?? 0,
  },
  tools: {
    count: toolCatalog.toolCount ?? 0,
  },
  retrieval: {
    chunkCount: retrievalIndex.chunkCount ?? 0,
    sourceCount: retrievalIndex.sourceCount ?? 0,
  },
  telemetry: {
    runCount: agentUsage.runCount ?? 0,
    finishedRunCount: agentUsage.finishedRunCount ?? 0,
    totalEstimatedTimeSavedMinutes: agentUsage.totalEstimatedTimeSavedMinutes ?? null,
    latestRun: latestRun ? {
      runId: latestRun.runId,
      agent: latestRun.agent,
      docsBeforeFirstEdit: latestRun.metrics?.docsBeforeFirstEdit ?? null,
      actualMinutes: latestRun.metrics?.actualMinutes ?? null,
      baselineMinutes: latestRun.metrics?.baselineMinutes ?? null,
      timeSavedMinutes: latestRun.metrics?.timeSavedMinutes ?? null,
    } : null,
  },
  ab: {
    comparisons: abRecords.length,
    routedWins: abRecords.filter((record) => record.routedWin).length,
  },
  feltChecks,
};

const markdown = [
  '# Context Value Demo',
  '',
  'This generated report is the fastest way to explain why the context system is useful in practice.',
  '',
  '## Why It Feels Different',
  '',
  `- You start from about \`${summary.smallMap.approxTokens}\` tokens instead of \`${summary.allDocs.approxTokens}\` across the broader docs set.`,
  `- You can discover \`${summary.registry.surfaceCount}\` surfaces, \`${summary.agents.count}\` reusable agents, and \`${summary.tools.count}\` reusable tools without replaying chat history.`,
  `- Ambiguous tasks can fall back to retrieval over \`${summary.retrieval.chunkCount}\` indexed chunks.`,
  `- Measured runtime evidence currently shows \`${formatNumber(summary.telemetry.totalEstimatedTimeSavedMinutes)}\` minutes of estimated time saved.`,
  `- Routed-vs-baseline evidence currently has \`${summary.ab.routedWins}\` wins across \`${summary.ab.comparisons}\` recorded comparisons.`,
  '',
  '## Felt Value Scorecard',
  '',
  '| Check | Result | Evidence |',
  '| --- | --- | --- |',
  ...summary.feltChecks.map((item) => `| ${item.label} | ${item.pass ? 'PASS' : 'NEEDS EVIDENCE'} | ${item.evidence} |`),
  '',
  '## Latest Measured Run',
  '',
  ...(summary.telemetry.latestRun
    ? [
        `- Run: \`${summary.telemetry.latestRun.runId}\``,
        `- Agent: \`${summary.telemetry.latestRun.agent}\``,
        `- Docs before first edit: \`${formatNumber(summary.telemetry.latestRun.docsBeforeFirstEdit)}\``,
        `- Actual minutes: \`${formatNumber(summary.telemetry.latestRun.actualMinutes)}\``,
        `- Baseline minutes: \`${formatNumber(summary.telemetry.latestRun.baselineMinutes)}\``,
        `- Estimated time saved: \`${formatNumber(summary.telemetry.latestRun.timeSavedMinutes)}\``,
      ]
    : ['- No measured runs recorded yet.']),
  '',
  '## Fast Demo Commands',
  '',
  '```bash',
  'npm run docs:check',
  'npm run registry:query -- --kind tool --q retrieve',
  'npm run registry:describe -- --kind tool --id context-retrieve',
  'npm run retrieve:query -- --q "routing rules"',
  'npm run agent:start -- --agent planner --surface core',
  'npm run agent:event -- --type doc_open --path docs/PLANS.md',
  'npm run agent:finish -- --status success --baseline-minutes 30',
  'npm run agent:report',
  'npm run value:demo',
  '```',
  '',
  '## Interpretation',
  '',
  '- If the small-map reduction is weak, the routing layer is still too fat.',
  '- If discovery counts are zero, outsiders will not feel the system yet.',
  '- If retrieval has no chunks, ambiguous work will still fall back to broad scanning.',
  '- If time-saved evidence is missing, users will read this as process overhead rather than leverage.',
  '- If there are no routed wins, the system may be tidy but still not feel faster.',
  '',
].join('\n') + '\n';

writeManaged(outputJsonPath, `${JSON.stringify(summary, null, 2)}\n`);
writeManaged(outputMarkdownPath, markdown);

if (!checkMode) {
  console.log(`[context-value-demo] wrote ${path.relative(rootDir, outputMarkdownPath)}`);
  console.log(`[context-value-demo] small map vs all docs: ${formatNumber(smallMapReductionVsAllDocsPct)}% smaller`);
  console.log(`[context-value-demo] time saved: ${formatNumber(summary.telemetry.totalEstimatedTimeSavedMinutes)}`);
}
