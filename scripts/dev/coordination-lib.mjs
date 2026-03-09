#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd,
    encoding: 'utf8',
    env: options.env ?? process.env,
    stdio: options.stdio ?? 'pipe',
  });
}

export function resolveRootDir(cwd = process.cwd()) {
  const result = run('git', ['rev-parse', '--show-toplevel'], { cwd });
  if (result.status !== 0) {
    throw new Error('[coordination] not inside a git repository');
  }
  return result.stdout.trim();
}

export function readJson(filePath) {
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
}

export function writeJson(filePath, value) {
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

export function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

export function sanitize(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
}

export function normalizeRepoPath(value) {
  return String(value).trim().replace(/\\/g, '/').replace(/^\.?\//, '').replace(/\/+$/, '');
}

export function pathOverlaps(left, right) {
  if (!left || !right) return false;
  return left === right || left.startsWith(`${right}/`) || right.startsWith(`${left}/`);
}

export function isWithinPrefix(target, prefix) {
  if (!target || !prefix) return false;
  return target === prefix || target.startsWith(`${prefix}/`);
}

export function isFeatureBranch(branch, prefixes) {
  return prefixes.some((prefix) => branch.startsWith(prefix));
}

export function repoHasRef(rootDir, ref) {
  return run('git', ['rev-parse', '--verify', ref], { cwd: rootDir }).status === 0;
}

export function repoHasHead(rootDir) {
  return repoHasRef(rootDir, 'HEAD');
}

export function currentBranch(rootDir) {
  return run('git', ['symbolic-ref', '--quiet', '--short', 'HEAD'], { cwd: rootDir }).stdout.trim() || 'HEAD';
}

export function loadConfig(rootDir) {
  return readJson(path.join(rootDir, 'context-kit.json'));
}

export function coordinationPaths(rootDir) {
  const coordinationDir = path.join(rootDir, '.agent-context', 'coordination');
  return {
    coordinationDir,
    claimsDir: path.join(coordinationDir, 'claims'),
    historyDir: path.join(coordinationDir, 'history'),
    branchesDir: path.join(coordinationDir, 'branches'),
    reportPath: path.join(coordinationDir, 'report.md'),
    eventsPath: path.join(coordinationDir, 'events.tsv'),
    lockPath: path.join(coordinationDir, 'claims.lock'),
  };
}

export function coordinationConfig(config) {
  return {
    requireClaimOnFeatureBranches: config.coordination?.requireClaimOnFeatureBranches ?? true,
    requirePathsOnFeatureBranches: config.coordination?.requirePathsOnFeatureBranches ?? true,
    featureBranchPrefixes: config.coordination?.featureBranchPrefixes ?? ['codex/'],
    defaultLeaseMinutes: Number(config.coordination?.defaultLeaseMinutes ?? 240),
    failOnExpiredClaims: config.coordination?.failOnExpiredClaims ?? true,
    failOnPathOverlap: config.coordination?.failOnPathOverlap ?? true,
    failOnUnscopedSurfaceOverlap: config.coordination?.failOnUnscopedSurfaceOverlap ?? true,
    sharedPathPrefixes: (config.coordination?.sharedPathPrefixes ?? ['docs/AGENT_WATCH_LOG.md', 'docs/generated/', '.agent-context/'])
      .map(normalizeRepoPath),
  };
}

export function readClaims(rootDir) {
  const { claimsDir } = coordinationPaths(rootDir);
  if (!fs.existsSync(claimsDir)) return [];
  return fs.readdirSync(claimsDir)
    .filter((name) => name.endsWith('.json'))
    .map((name) => readJson(path.join(claimsDir, name)))
    .sort((a, b) => String(a.workId ?? '').localeCompare(String(b.workId ?? '')))
    .map((claim) => ({
      ...claim,
      paths: [...new Set((claim.paths ?? []).map(normalizeRepoPath).filter(Boolean))],
      docs: [...new Set((claim.docs ?? []).map(normalizeRepoPath).filter(Boolean))],
    }));
}

export function appendCoordinationEvent(rootDir, row) {
  const { eventsPath } = coordinationPaths(rootDir);
  ensureDir(path.dirname(eventsPath));
  if (!fs.existsSync(eventsPath)) {
    fs.writeFileSync(eventsPath, 'timestamp\tevent\twork_id\tbranch\tagent\tsurface\tpath\n');
  }
  fs.appendFileSync(eventsPath, `${row.join('\t')}\n`);
}

export function withCoordinationLock(rootDir, fn) {
  const { lockPath } = coordinationPaths(rootDir);
  const config = coordinationConfig(loadConfig(rootDir));
  const staleMinutes = Number(config.lockStaleMinutes ?? 15);
  const staleAgeMs = Number.isFinite(staleMinutes) && staleMinutes > 0 ? staleMinutes * 60 * 1000 : 15 * 60 * 1000;
  ensureDir(path.dirname(lockPath));
  let fd;

  function tryAcquireLock() {
    return fs.openSync(lockPath, 'wx');
  }

  try {
    fd = tryAcquireLock();
  } catch (error) {
    if (error && error.code === 'EEXIST') {
      try {
        const stats = fs.statSync(lockPath);
        if ((Date.now() - stats.mtimeMs) > staleAgeMs) {
          fs.rmSync(lockPath, { force: true });
          fd = tryAcquireLock();
        } else {
          throw new Error('[coordination] another coordination operation is in progress; retry in a moment');
        }
      } catch (retryError) {
        if (retryError instanceof Error) throw retryError;
        throw new Error('[coordination] another coordination operation is in progress; retry in a moment');
      }
    } else {
      throw error;
    }
  }

  try {
    fs.writeSync(fd, JSON.stringify({ pid: process.pid, createdAt: new Date().toISOString() }));
    return fn();
  } finally {
    fs.closeSync(fd);
    fs.rmSync(lockPath, { force: true });
  }
}

function gitNames(rootDir, args) {
  const result = run('git', args, { cwd: rootDir });
  if (result.status !== 0) return [];
  return `${result.stdout || ''}`
    .split('\n')
    .map((line) => normalizeRepoPath(line))
    .filter(Boolean);
}

export function listChangedFiles(rootDir, mainBranch) {
  const files = new Set();
  const preferredBaseRefs = [`origin/${mainBranch}`, mainBranch];
  const baseRef = preferredBaseRefs.find((ref) => repoHasRef(rootDir, ref)) ?? null;

  if (repoHasHead(rootDir) && baseRef) {
    for (const item of gitNames(rootDir, ['diff', '--name-only', '--relative', `${baseRef}...HEAD`])) {
      files.add(item);
    }
  }

  for (const item of gitNames(rootDir, ['diff', '--name-only', '--relative'])) {
    files.add(item);
  }
  for (const item of gitNames(rootDir, ['diff', '--name-only', '--cached', '--relative'])) {
    files.add(item);
  }
  for (const item of gitNames(rootDir, ['ls-files', '--others', '--exclude-standard'])) {
    files.add(item);
  }

  return [...files].sort();
}

export function validateSurfaceId(config, surface) {
  const surfaceIds = new Set((config.surfaces ?? []).map((item) => item.id).filter(Boolean));
  if (surfaceIds.size === 0) return;
  if (!surfaceIds.has(surface)) {
    throw new Error(`[coordination] unknown surface: ${surface}`);
  }
}

export function filteredClaimPaths(claim, coordination) {
  return (claim.paths ?? []).filter((item) => !coordination.sharedPathPrefixes.some((prefix) => isWithinPrefix(item, prefix)));
}

export function collectCoordinationIssues({
  claims,
  coordination,
  currentBranchName,
  changedFiles = [],
}) {
  const failures = [];
  const warnings = [];

  if (
    currentBranchName &&
    coordination.requireClaimOnFeatureBranches &&
    isFeatureBranch(currentBranchName, coordination.featureBranchPrefixes)
  ) {
    const branchClaims = claims.filter((claim) => claim.branch === currentBranchName);
    if (branchClaims.length === 0) {
      failures.push(`feature branch \`${currentBranchName}\` has no active coordination claim`);
    }
  }

  const activeClaimsByBranch = new Map();
  for (const claim of claims) {
    const items = activeClaimsByBranch.get(claim.branch) ?? [];
    items.push(claim);
    activeClaimsByBranch.set(claim.branch, items);

    if (coordination.failOnExpiredClaims && claim.leaseExpiresAt) {
      const expiry = Date.parse(claim.leaseExpiresAt);
      if (Number.isFinite(expiry) && expiry < Date.now()) {
        failures.push(`claim \`${claim.workId}\` on branch \`${claim.branch}\` has expired lease \`${claim.leaseExpiresAt}\``);
      }
    }
  }

  for (const [branch, branchClaims] of activeClaimsByBranch.entries()) {
    if (branchClaims.length > 1) {
      failures.push(`branch \`${branch}\` has multiple active claims: ${branchClaims.map((claim) => `\`${claim.workId}\``).join(', ')}`);
    }
  }

  for (let index = 0; index < claims.length; index += 1) {
    for (let cursor = index + 1; cursor < claims.length; cursor += 1) {
      const left = claims[index];
      const right = claims[cursor];
      const leftPaths = filteredClaimPaths(left, coordination);
      const rightPaths = filteredClaimPaths(right, coordination);
      const overlappingPaths = [];

      if (coordination.failOnPathOverlap) {
        for (const leftPath of leftPaths) {
          for (const rightPath of rightPaths) {
            if (pathOverlaps(leftPath, rightPath)) {
              overlappingPaths.push(`${leftPath} <-> ${rightPath}`);
            }
          }
        }
        if (overlappingPaths.length > 0) {
          failures.push(`claims \`${left.workId}\` and \`${right.workId}\` overlap on path boundaries: ${overlappingPaths.join(', ')}`);
        }
      }

      if (
        coordination.failOnUnscopedSurfaceOverlap &&
        left.surface &&
        left.surface === right.surface &&
        (leftPaths.length === 0 || rightPaths.length === 0)
      ) {
        failures.push(`claims \`${left.workId}\` and \`${right.workId}\` share surface \`${left.surface}\` without explicit path boundaries on both sides`);
      } else if (left.surface && left.surface === right.surface) {
        warnings.push(`claims \`${left.workId}\` and \`${right.workId}\` share surface \`${left.surface}\`; verify product-level coupling is still safe`);
      }
    }
  }

  if (currentBranchName) {
    const branchClaims = claims.filter((claim) => claim.branch === currentBranchName);
    if (branchClaims.length === 1) {
      const claim = branchClaims[0];
      const claimPaths = filteredClaimPaths(claim, coordination);
      const relevantChangedFiles = changedFiles
        .map(normalizeRepoPath)
        .filter(Boolean)
        .filter((filePath) => !coordination.sharedPathPrefixes.some((prefix) => isWithinPrefix(filePath, prefix)));

      if (
        coordination.requirePathsOnFeatureBranches &&
        isFeatureBranch(currentBranchName, coordination.featureBranchPrefixes) &&
        claimPaths.length === 0 &&
        relevantChangedFiles.length > 0
      ) {
        failures.push(`branch \`${currentBranchName}\` has changed files outside shared prefixes but claim \`${claim.workId}\` has no explicit path boundaries`);
      }

      if (claimPaths.length > 0) {
        const outOfScope = relevantChangedFiles.filter((filePath) => !claimPaths.some((prefix) => pathOverlaps(filePath, prefix)));
        if (outOfScope.length > 0) {
          failures.push(`branch \`${currentBranchName}\` changed files outside claim \`${claim.workId}\`: ${outOfScope.map((item) => `\`${item}\``).join(', ')}`);
        }
      }
    }
  }

  return { failures, warnings };
}
