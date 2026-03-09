#!/usr/bin/env node
import { currentBranch, readClaims, resolveRootDir } from './coordination-lib.mjs';

const rootDir = resolveRootDir();
const branch = currentBranch(rootDir);
const currentOnly = process.argv.includes('--current-branch');
const claims = readClaims(rootDir).filter((claim) => !currentOnly || claim.branch === branch);

if (claims.length === 0) {
  console.log('[coord:list] no active claims');
  process.exit(0);
}

console.log('work_id\tbranch\tagent\tsurface\tlease_expires_at\tpaths');
for (const claim of claims) {
  console.log([
    claim.workId,
    claim.branch,
    claim.agent,
    claim.surface,
    claim.leaseExpiresAt,
    (claim.paths ?? []).join(',') || '-',
  ].join('\t'));
}
