#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const configPath = path.join(rootDir, 'context-kit.json');
const outputPath = path.join(rootDir, 'docs/generated/claude-compatibility-bootstrap.md');
const checkMode = process.argv.includes('--check');

const defaultRiskHints = [
  { dir: 'src/auth', reason: 'authentication and authorization boundary' },
  { dir: 'src/persistence', reason: 'persistence and data consistency boundary' },
  { dir: 'src/payments', reason: 'payment and billing boundary' },
  { dir: 'src/billing', reason: 'billing and subscription boundary' },
  { dir: 'src/migrations', reason: 'schema or data migration boundary' },
  { dir: 'src/db', reason: 'database access boundary' },
  { dir: 'src/database', reason: 'database access boundary' },
  { dir: 'infra', reason: 'infrastructure and deployment boundary' },
  { dir: 'migrations', reason: 'schema or data migration boundary' },
  { dir: 'db', reason: 'database boundary' },
  { dir: 'database', reason: 'database boundary' },
  { dir: 'payments', reason: 'payment and billing boundary' },
  { dir: 'billing', reason: 'billing boundary' },
  { dir: 'terraform', reason: 'infrastructure as code boundary' },
  { dir: 'prisma', reason: 'schema and migration boundary' }
];

function readJson(filePath, fallback = {}) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeManaged(filePath, content) {
  const existing = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null;
  if (checkMode) {
    if (existing !== content) {
      throw new Error(`[claude:bootstrap] stale generated file: ${path.relative(rootDir, filePath)}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

function normalize(relPath) {
  return relPath.split(path.sep).join('/');
}

function uniqueHints(config) {
  const configured = Array.isArray(config.claude?.riskyPathHints)
    ? config.claude.riskyPathHints.map((dir) => ({ dir, reason: 'project-configured high-risk boundary' }))
    : [];

  const merged = [...defaultRiskHints, ...configured];
  const seen = new Set();
  return merged.filter((item) => {
    const key = normalize(item.dir);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function localClaudeTemplate(relDir, reason) {
  return [
    '# CLAUDE.md',
    '',
    'This directory is higher risk than the average repository surface.',
    '',
    '## Why This Area Is Sensitive',
    `- Primary reason: ${reason}.`,
    '- Changes here can affect correctness, safety, or irreversible system behavior.',
    '',
    '## Before You Edit',
    '1. Re-read `README.md`, `AGENTS.md`, and `docs/README.md`.',
    '2. Re-read `docs/SECURITY.md`, `docs/RELIABILITY.md`, and `docs/GIT_WORKFLOW.md`.',
    '3. Open the smallest relevant canonical docs before touching code.',
    '4. Prefer the smallest safe change that preserves current invariants.',
    '',
    '## Local Risks',
    '- Replace this placeholder with directory-specific failure modes.',
    '- Replace this placeholder with nearby invariants or irreversible actions.',
    '',
    '## Required Checks',
    '- `npm run docs:check`',
    '- `npm run ctx:check -- --strict`',
    '- Add project-specific build/test gates here if this directory requires them.',
    '',
    '## Escalate Before',
    '- schema or migration changes',
    '- auth boundary changes',
    '- secret or credential handling changes',
    '- destructive backfills or irreversible infrastructure changes',
    '',
    `## Local Scope`,
    `- Directory: \`${relDir}\``,
    '',
  ].join('\n') + '\n';
}

const config = readJson(configPath, {});
const hints = uniqueHints(config);
const created = [];
const present = [];
const missing = [];

for (const hint of hints) {
  const relDir = normalize(hint.dir);
  const absDir = path.join(rootDir, relDir);
  if (!fs.existsSync(absDir) || !fs.statSync(absDir).isDirectory()) continue;

  const claudePath = path.join(absDir, 'CLAUDE.md');
  if (fs.existsSync(claudePath)) {
    present.push({ relDir, reason: hint.reason, file: normalize(path.relative(rootDir, claudePath)) });
    continue;
  }

  if (checkMode) {
    missing.push({ relDir, reason: hint.reason, file: normalize(path.relative(rootDir, claudePath)) });
    continue;
  }

  fs.writeFileSync(claudePath, localClaudeTemplate(relDir, hint.reason));
  created.push({ relDir, reason: hint.reason, file: normalize(path.relative(rootDir, claudePath)) });
}

if (checkMode && missing.length > 0) {
  throw new Error(
    `[claude:bootstrap] missing local CLAUDE.md for risky directories: ${missing.map((item) => item.file).join(', ')}`,
  );
}

const report = [
  '# Claude Compatibility Bootstrap',
  '',
  'This report explains which Claude-native compatibility files were seeded or detected.',
  '',
  '## Static Layer',
  '',
  '- Root compatibility doc: `docs/CLAUDE_COMPATIBILITY.md`',
  '- Claude routing doc: `.claude/README.md`',
  '- Claude agents: `.claude/agents/`',
  '- Claude commands: `.claude/commands/`',
  '- Claude hooks: `.claude/hooks/`',
  '- Claude hook settings: `.claude/settings.json`',
  '',
  '## Risky Local Guidance',
  '',
  `- Risky directories detected: \`${created.length + present.length}\``,
  `- Local guides currently present: \`${created.length + present.length}\``,
  `- Local guides missing: \`${missing.length}\``,
  '',
  '### Present Guides',
  ...(
    created.length || present.length
      ? [...present, ...created].sort((left, right) => left.file.localeCompare(right.file)).map((item) => `- \`${item.file}\` -> ${item.reason}`)
      : ['- none']
  ),
  '',
  '## Next Steps',
  '',
  '- Fill any placeholder `Local Risks` sections in newly created local `CLAUDE.md` files.',
  '- Keep root `CLAUDE.md` concise and navigational.',
  '- Promote stable reusable workflows into `.claude/commands/` or `.claude/agents/`.',
  '- Keep deterministic automation in `.claude/hooks/` and expensive validation in git hooks or explicit gates.',
  '',
].join('\n') + '\n';

writeManaged(outputPath, report);
process.stdout.write(`[claude:bootstrap] wrote ${path.relative(rootDir, outputPath)}\n`);
if (!checkMode && created.length > 0) {
  process.stdout.write(`[claude:bootstrap] created ${created.length} local CLAUDE.md file(s)\n`);
}
