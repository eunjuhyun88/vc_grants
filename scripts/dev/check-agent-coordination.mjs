#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {
  collectCoordinationIssues,
  coordinationConfig,
  coordinationPaths,
  currentBranch,
  ensureDir,
  loadConfig,
  listChangedFiles,
  readClaims,
  resolveRootDir,
} from './coordination-lib.mjs';

const rootDir = resolveRootDir();
const config = loadConfig(rootDir);
const coordination = coordinationConfig(config);
const claims = readClaims(rootDir);
const currentBranchName = currentBranch(rootDir);
const mainBranch = config.git?.mainBranch || 'main';
const changedFiles = listChangedFiles(rootDir, mainBranch);
const { failures, warnings } = collectCoordinationIssues({
  claims,
  coordination,
  currentBranchName,
  changedFiles,
});
const { coordinationDir, reportPath } = coordinationPaths(rootDir);

ensureDir(coordinationDir);

const reportLines = [
  '# Coordination Report',
  '',
  `- Current branch: \`${currentBranchName}\``,
  `- Active claims: \`${claims.length}\``,
  '',
  '## Active Claims',
  '',
  '| Work ID | Branch | Agent | Surface | Lease Expires | Paths |',
  '| --- | --- | --- | --- | --- | --- |',
  ...(
    claims.length > 0
      ? claims.map((claim) => `| \`${claim.workId}\` | \`${claim.branch}\` | \`${claim.agent}\` | \`${claim.surface}\` | \`${claim.leaseExpiresAt ?? 'n/a'}\` | ${(claim.paths ?? []).map((item) => `\`${item}\``).join(', ') || '-'} |`)
      : ['| none | - | - | - | - | - |']
  ),
  '',
  '## Current Branch Changed Files',
  '',
  ...(changedFiles.length > 0 ? changedFiles.map((item) => `- \`${item}\``) : ['- none']),
  '',
  '## Failures',
  '',
  ...(failures.length > 0 ? failures.map((item) => `- ${item}`) : ['- none']),
  '',
  '## Warnings',
  '',
  ...(warnings.length > 0 ? warnings.map((item) => `- ${item}`) : ['- none']),
  '',
];
fs.writeFileSync(reportPath, `${reportLines.join('\n')}\n`);

if (failures.length > 0) {
  for (const failure of failures) {
    console.error(`[coord:check] fail: ${failure}`);
  }
  for (const warning of warnings) {
    console.error(`[coord:check] warn: ${warning}`);
  }
  console.error(`[coord:check] report: ${path.relative(rootDir, reportPath)}`);
  process.exit(1);
}

for (const warning of warnings) {
  console.log(`[coord:check] warn: ${warning}`);
}
console.log('[coord:check] coordination checks passed.');
console.log(`[coord:check] report: ${path.relative(rootDir, reportPath)}`);
