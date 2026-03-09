#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {
  appendCoordinationEvent,
  coordinationPaths,
  ensureDir,
  readClaims,
  resolveRootDir,
  sanitize,
  withCoordinationLock,
  writeJson,
} from './coordination-lib.mjs';

function usage() {
  console.log('Usage: node scripts/dev/release-work.mjs --work-id <id> [--status <done|handoff|abandoned>] [--note <text>] [--handoff-to <agent>]');
}

const rootDir = resolveRootDir();
const args = process.argv.slice(2);
const options = {
  workId: '',
  status: 'done',
  note: '',
  handoffTo: '',
};

for (let index = 0; index < args.length; index += 1) {
  const current = args[index];
  const next = args[index + 1];
  if (current === '--work-id') {
    options.workId = next ?? '';
    index += 1;
    continue;
  }
  if (current === '--status') {
    options.status = next ?? options.status;
    index += 1;
    continue;
  }
  if (current === '--note') {
    options.note = next ?? '';
    index += 1;
    continue;
  }
  if (current === '--handoff-to') {
    options.handoffTo = next ?? '';
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    usage();
    process.exit(0);
  }
  throw new Error(`[coord:release] unknown option: ${current}`);
}

if (!options.workId) {
  usage();
  process.exit(1);
}
if (!['done', 'handoff', 'abandoned'].includes(options.status)) {
  throw new Error('[coord:release] status must be done, handoff, or abandoned');
}
if (options.status === 'handoff' && !options.handoffTo) {
  throw new Error('[coord:release] --handoff-to is required when status=handoff');
}

withCoordinationLock(rootDir, () => {
  const { claimsDir, historyDir, branchesDir } = coordinationPaths(rootDir);
  const claim = readClaims(rootDir).find((item) => item.workId === options.workId);
  if (!claim) {
    throw new Error(`[coord:release] active claim not found: ${options.workId}`);
  }

  const timestamp = new Date().toISOString();
  const workSafe = sanitize(options.workId);
  const branchSafe = sanitize(String(claim.branch ?? '').replaceAll('/', '-'));
  const claimPath = path.join(claimsDir, `${workSafe}.json`);
  const branchPath = path.join(branchesDir, `${branchSafe}.json`);
  const historyPath = path.join(historyDir, `${workSafe}-${timestamp.replace(/[:]/g, '-')}.json`);
  ensureDir(historyDir);

  const released = {
    ...claim,
    status: options.status,
    releasedAt: timestamp,
    releaseNote: options.note,
    handoffTo: options.handoffTo || null,
  };

  writeJson(historyPath, released);
  writeJson(path.join(historyDir, `${workSafe}-latest.json`), released);

  fs.rmSync(claimPath, { force: true });

  if (fs.existsSync(branchPath)) {
    try {
      const branchPointer = JSON.parse(fs.readFileSync(branchPath, 'utf8'));
      if (branchPointer.workId === claim.workId) {
        fs.rmSync(branchPath, { force: true });
      }
    } catch {
      fs.rmSync(branchPath, { force: true });
    }
  }

  appendCoordinationEvent(rootDir, [timestamp, 'release', claim.workId, claim.branch ?? '-', claim.agent ?? '-', claim.surface ?? '-', options.status]);
  console.log(`[coord:release] archived: ${path.relative(rootDir, historyPath)}`);
  console.log(`[coord:release] status: ${options.status}`);
});
