#!/usr/bin/env node
import path from 'node:path';
import {
  appendCoordinationEvent,
  collectCoordinationIssues,
  coordinationConfig,
  coordinationPaths,
  currentBranch,
  ensureDir,
  loadConfig,
  readClaims,
  resolveRootDir,
  sanitize,
  validateSurfaceId,
  withCoordinationLock,
  writeJson,
  normalizeRepoPath,
  isFeatureBranch,
} from './coordination-lib.mjs';

function usage() {
  console.log('Usage: node scripts/dev/claim-work.mjs --work-id <id> --agent <name> --surface <surface> --summary <text> [--path <prefix>] [--doc <path>] [--depends-on <id>] [--lease-minutes <n>] [--status <active|blocked>]');
}

const rootDir = resolveRootDir();
const args = process.argv.slice(2);
const options = {
  workId: '',
  agent: process.env.USER || 'agent',
  surface: '',
  summary: '',
  leaseMinutes: null,
  status: 'active',
  paths: [],
  docs: [],
  dependsOn: [],
};

for (let index = 0; index < args.length; index += 1) {
  const current = args[index];
  const next = args[index + 1];
  if (current === '--work-id') {
    options.workId = next ?? '';
    index += 1;
    continue;
  }
  if (current === '--agent') {
    options.agent = next ?? options.agent;
    index += 1;
    continue;
  }
  if (current === '--surface') {
    options.surface = next ?? '';
    index += 1;
    continue;
  }
  if (current === '--summary') {
    options.summary = next ?? '';
    index += 1;
    continue;
  }
  if (current === '--lease-minutes') {
    options.leaseMinutes = Number(next ?? '');
    index += 1;
    continue;
  }
  if (current === '--status') {
    options.status = next ?? options.status;
    index += 1;
    continue;
  }
  if (current === '--path') {
    options.paths.push(next ?? '');
    index += 1;
    continue;
  }
  if (current === '--doc') {
    options.docs.push(next ?? '');
    index += 1;
    continue;
  }
  if (current === '--depends-on') {
    options.dependsOn.push(next ?? '');
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    usage();
    process.exit(0);
  }
  throw new Error(`[coord:claim] unknown option: ${current}`);
}

if (!options.workId || !options.surface || !options.summary) {
  usage();
  process.exit(1);
}
if (!['active', 'blocked'].includes(options.status)) {
  throw new Error('[coord:claim] status must be active or blocked');
}

const config = loadConfig(rootDir);
const coordination = coordinationConfig(config);
validateSurfaceId(config, options.surface);

const branch = currentBranch(rootDir);
if (
  coordination.requirePathsOnFeatureBranches &&
  isFeatureBranch(branch, coordination.featureBranchPrefixes) &&
  options.paths.length === 0
) {
  throw new Error(`[coord:claim] feature branch \`${branch}\` requires at least one --path boundary`);
}

const leaseMinutes = Number.isFinite(options.leaseMinutes) && options.leaseMinutes > 0
  ? options.leaseMinutes
  : coordination.defaultLeaseMinutes;

withCoordinationLock(rootDir, () => {
  const timestamp = new Date().toISOString();
  const leaseExpiresAt = new Date(Date.now() + leaseMinutes * 60 * 1000).toISOString();
  const workSafe = sanitize(options.workId);
  const branchSafe = sanitize(branch.replaceAll('/', '-'));
  const { claimsDir, branchesDir } = coordinationPaths(rootDir);
  const claimPath = path.join(claimsDir, `${workSafe}.json`);
  const branchPath = path.join(branchesDir, `${branchSafe}.json`);
  const existing = readClaims(rootDir).find((claim) => claim.workId === options.workId) ?? null;

  const claim = {
    version: 1,
    workId: options.workId,
    agent: options.agent,
    surface: options.surface,
    summary: options.summary,
    branch,
    worktree: process.cwd(),
    status: options.status,
    leaseMinutes,
    claimedAt: existing?.claimedAt ?? timestamp,
    updatedAt: timestamp,
    leaseExpiresAt,
    paths: [...new Set(options.paths.map(normalizeRepoPath).filter(Boolean))],
    docs: [...new Set(options.docs.map(normalizeRepoPath).filter(Boolean))],
    dependsOn: [...new Set(options.dependsOn.filter(Boolean))],
  };

  const otherClaims = readClaims(rootDir).filter((item) => item.workId !== claim.workId);
  const sameWorkDifferentBranch = readClaims(rootDir).find((item) => item.workId === claim.workId && item.branch !== branch);
  if (sameWorkDifferentBranch) {
    throw new Error(`[coord:claim] work ID \`${claim.workId}\` is already claimed on branch \`${sameWorkDifferentBranch.branch}\``);
  }

  const { failures } = collectCoordinationIssues({
    claims: [...otherClaims, claim],
    coordination,
    currentBranchName: branch,
    changedFiles: [],
  });
  if (failures.length > 0) {
    throw new Error(`[coord:claim] rejected:\n- ${failures.join('\n- ')}`);
  }

  ensureDir(claimsDir);
  ensureDir(branchesDir);
  writeJson(claimPath, claim);
  writeJson(branchPath, { workId: claim.workId, branch, updatedAt: timestamp });
  appendCoordinationEvent(rootDir, [timestamp, 'claim', claim.workId, branch, claim.agent, claim.surface, claim.paths.join(',') || '-']);

  console.log(`[coord:claim] saved: ${path.relative(rootDir, claimPath)}`);
  console.log(`[coord:claim] branch: ${branch}`);
  console.log(`[coord:claim] surface: ${claim.surface}`);
  console.log(`[coord:claim] lease expires: ${claim.leaseExpiresAt}`);
});
