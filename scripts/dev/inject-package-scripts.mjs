#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const targetDir = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd();
const overwriteManaged = process.argv.includes('--overwrite-managed');
const packagePath = path.join(targetDir, 'package.json');
const nameFallback = path.basename(targetDir).toLowerCase().replace(/[^a-z0-9]+/g, '-');

const scripts = {
  'docs:refresh': 'node scripts/dev/refresh-generated-context.mjs && node scripts/dev/refresh-context-retrieval.mjs && node scripts/dev/refresh-agent-catalog.mjs && node scripts/dev/refresh-tool-catalog.mjs && node scripts/dev/refresh-agent-usage-report.mjs && node scripts/dev/refresh-context-registry.mjs && node scripts/dev/refresh-context-ab-report.mjs && node scripts/dev/refresh-sandbox-policy-report.mjs && node scripts/dev/refresh-doc-governance.mjs && node scripts/dev/refresh-context-metrics.mjs && node scripts/dev/refresh-context-value-demo.mjs',
  'docs:refresh:check': 'node scripts/dev/refresh-generated-context.mjs --check && node scripts/dev/refresh-context-retrieval.mjs --check && node scripts/dev/refresh-agent-catalog.mjs --check && node scripts/dev/refresh-tool-catalog.mjs --check && node scripts/dev/refresh-agent-usage-report.mjs --check && node scripts/dev/refresh-context-registry.mjs --check && node scripts/dev/refresh-context-ab-report.mjs --check && node scripts/dev/refresh-sandbox-policy-report.mjs --check && node scripts/dev/refresh-doc-governance.mjs --check && node scripts/dev/refresh-context-metrics.mjs --check && node scripts/dev/refresh-context-value-demo.mjs --check',
  'docs:check': 'bash scripts/dev/check-docs-context.sh',
  'gate:context': 'npm run docs:check && npm run ctx:check -- --strict && npm run coord:check && npm run sandbox:check',
  'safe:status': 'bash scripts/dev/safe-status.sh',
  'safe:worktree': 'bash scripts/dev/new-worktree.sh',
  'safe:hooks': 'bash scripts/dev/install-git-hooks.sh',
  'safe:git-config': 'bash scripts/dev/bootstrap-git-config.sh',
  'safe:sync': 'bash scripts/dev/sync-branch.sh',
  'safe:sync:gate': 'bash scripts/dev/sync-branch.sh --gate',
  'ctx:save': 'bash scripts/dev/context-save.sh',
  'ctx:checkpoint': 'bash scripts/dev/context-checkpoint.sh',
  'ctx:compact': 'bash scripts/dev/context-compact.sh',
  'ctx:check': 'bash scripts/dev/check-context-quality.sh',
  'ctx:restore': 'bash scripts/dev/context-restore.sh',
  'ctx:pin': 'bash scripts/dev/context-pin.sh',
  'ctx:auto': 'bash scripts/dev/context-auto.sh',
  'adopt:bootstrap': 'node scripts/dev/bootstrap-project-truth.mjs && node scripts/dev/bootstrap-claude-compat.mjs',
  'claude:bootstrap': 'node scripts/dev/bootstrap-claude-compat.mjs',
  'coord:claim': 'node scripts/dev/claim-work.mjs',
  'coord:list': 'node scripts/dev/list-work-claims.mjs',
  'coord:check': 'node scripts/dev/check-agent-coordination.mjs',
  'coord:release': 'node scripts/dev/release-work.mjs',
  'agent:refresh': 'node scripts/dev/refresh-agent-catalog.mjs && node scripts/dev/refresh-context-registry.mjs',
  'agent:new': 'node scripts/dev/scaffold-agent.mjs',
  'agent:start': 'node scripts/dev/start-agent-run.mjs',
  'agent:event': 'node scripts/dev/log-agent-event.mjs',
  'agent:finish': 'node scripts/dev/finish-agent-run.mjs',
  'agent:report': 'node scripts/dev/refresh-agent-usage-report.mjs',
  'tool:refresh': 'node scripts/dev/refresh-tool-catalog.mjs && node scripts/dev/refresh-context-registry.mjs',
  'tool:new': 'node scripts/dev/scaffold-tool.mjs',
  'registry:refresh': 'node scripts/dev/refresh-context-registry.mjs',
  'registry:query': 'node scripts/dev/query-context-registry.mjs',
  'registry:describe': 'node scripts/dev/describe-context-entry.mjs',
  'registry:serve': 'node scripts/dev/serve-context-registry.mjs',
  'retrieve:refresh': 'node scripts/dev/refresh-context-retrieval.mjs',
  'retrieve:query': 'node scripts/dev/query-context-retrieval.mjs',
  'eval:ab:record': 'node scripts/dev/record-context-ab-eval.mjs',
  'eval:ab:refresh': 'node scripts/dev/refresh-context-ab-report.mjs',
  'value:demo': 'node scripts/dev/refresh-context-value-demo.mjs',
  'sandbox:check': 'node scripts/dev/refresh-sandbox-policy-report.mjs --validate-only',
  'harness:smoke': 'bash scripts/dev/run-context-harness.sh',
  'harness:browser': 'bash scripts/dev/run-browser-context-harness.sh',
  'harness:all': 'bash scripts/dev/run-full-context-harness.sh',
  'harness:benchmark': 'node scripts/dev/run-context-benchmark.mjs'
};

let pkg = {};
if (fs.existsSync(packagePath)) {
  pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
} else {
  pkg = {
    name: nameFallback,
    private: true,
    version: '0.0.0'
  };
}

pkg.scripts = pkg.scripts ?? {};
for (const [key, value] of Object.entries(scripts)) {
  if (overwriteManaged || !(key in pkg.scripts)) {
    pkg.scripts[key] = value;
  }
}

fs.writeFileSync(packagePath, `${JSON.stringify(pkg, null, 2)}\n`);
console.log(`[inject-package-scripts] updated ${packagePath}`);
