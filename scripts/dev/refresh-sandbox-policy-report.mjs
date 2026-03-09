#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const configPath = path.join(rootDir, 'context-kit.json');
const outputPath = path.join(rootDir, 'docs/generated/sandbox-policy-report.md');
const checkMode = process.argv.includes('--check');
const validateOnly = process.argv.includes('--validate-only');

function readJson(filePath) {
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
}

function hasWildcard(items) {
  return items.some((item) => String(item).includes('*'));
}

const config = readJson(configPath);
const policy = config.sandbox ?? {};
const errors = [];
const checks = [];

function validate(label, passed) {
  checks.push({ label, passed });
  if (!passed) errors.push(label);
}

validate('sandbox.enabled is true', policy.enabled === true);
validate('allowReadPaths is non-empty', Array.isArray(policy.allowReadPaths) && policy.allowReadPaths.length > 0);
validate('allowWritePaths is non-empty', Array.isArray(policy.allowWritePaths) && policy.allowWritePaths.length > 0);
validate('allowNetworkHosts is non-empty', Array.isArray(policy.allowNetworkHosts) && policy.allowNetworkHosts.length > 0);
validate('denyCommandPrefixes is non-empty', Array.isArray(policy.denyCommandPrefixes) && policy.denyCommandPrefixes.length > 0);
validate('denyCommandPrefixes includes `rm -rf`', Array.isArray(policy.denyCommandPrefixes) && policy.denyCommandPrefixes.includes('rm -rf'));
validate('denyCommandPrefixes includes `git reset --hard`', Array.isArray(policy.denyCommandPrefixes) && policy.denyCommandPrefixes.includes('git reset --hard'));
validate('allowWritePaths does not use wildcard `*`', Array.isArray(policy.allowWritePaths) && !hasWildcard(policy.allowWritePaths));
validate('allowNetworkHosts does not use wildcard `*`', Array.isArray(policy.allowNetworkHosts) && !hasWildcard(policy.allowNetworkHosts));

const content = [
  '# Sandbox Policy Report',
  '',
  'This report summarizes the repo-local sandbox policy used to keep agent execution bounded.',
  '',
  '## Policy Summary',
  '',
  `- Sandbox enabled: \`${policy.enabled === true ? 'yes' : 'no'}\``,
  `- Approval-required prefixes: \`${(policy.requireApprovalCommandPrefixes ?? []).join(', ') || 'none'}\``,
  `- Credential env allowlist size: \`${(policy.credentialEnvAllowlist ?? []).length}\``,
  '',
  '## Checks',
  '',
  ...checks.map((item) => `- ${item.passed ? 'PASS' : 'FAIL'}: ${item.label}`),
  '',
  '## Read Paths',
  '',
  ...((policy.allowReadPaths ?? []).length ? policy.allowReadPaths.map((item) => `- \`${item}\``) : ['- none']),
  '',
  '## Write Paths',
  '',
  ...((policy.allowWritePaths ?? []).length ? policy.allowWritePaths.map((item) => `- \`${item}\``) : ['- none']),
  '',
  '## Allowed Network Hosts',
  '',
  ...((policy.allowNetworkHosts ?? []).length ? policy.allowNetworkHosts.map((item) => `- \`${item}\``) : ['- none']),
  '',
  '## Denied Command Prefixes',
  '',
  ...((policy.denyCommandPrefixes ?? []).length ? policy.denyCommandPrefixes.map((item) => `- \`${item}\``) : ['- none']),
  '',
].join('\n') + '\n';

if (errors.length > 0) {
  throw new Error(`[sandbox] invalid sandbox policy:\n- ${errors.join('\n- ')}`);
}

if (validateOnly) {
  console.log('[sandbox] sandbox policy checks passed.');
  process.exit(0);
}

if (checkMode) {
  const existing = fs.existsSync(outputPath) ? fs.readFileSync(outputPath, 'utf8') : null;
  if (existing !== content) {
    throw new Error('[sandbox] stale generated file: docs/generated/sandbox-policy-report.md');
  }
} else {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, content);
}
