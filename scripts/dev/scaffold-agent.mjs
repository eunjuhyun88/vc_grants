#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { agentDir, loadAgentConfig } from './agent-catalog-lib.mjs';

const rootDir = process.cwd();
const { surfaces, agentConfig } = loadAgentConfig(rootDir);
const options = {
  id: '',
  role: 'implementer',
  surface: agentConfig.defaultSurface,
  name: '',
  summary: '',
};

for (let index = 2; index < process.argv.length; index += 1) {
  const current = process.argv[index];
  if (current === '--id') {
    options.id = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--role') {
    options.role = process.argv[index + 1] ?? options.role;
    index += 1;
    continue;
  }
  if (current === '--surface') {
    options.surface = process.argv[index + 1] ?? options.surface;
    index += 1;
    continue;
  }
  if (current === '--name') {
    options.name = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '--summary') {
    options.summary = process.argv[index + 1] ?? '';
    index += 1;
    continue;
  }
  if (current === '-h' || current === '--help') {
    console.log('Usage: node scripts/dev/scaffold-agent.mjs --id <agent-id> [--role planner|implementer|reviewer] [--surface <surface>] [--name <name>] [--summary <text>]');
    process.exit(0);
  }
  throw new Error(`[agent:new] unknown option: ${current}`);
}

if (!options.id) {
  throw new Error('[agent:new] missing required flag: --id');
}
if (!surfaces.includes(options.surface)) {
  throw new Error(`[agent:new] unknown surface: ${options.surface}`);
}
if (!/^[a-z0-9][a-z0-9-]*$/.test(options.id)) {
  throw new Error('[agent:new] id must match ^[a-z0-9][a-z0-9-]*$');
}

const presets = {
  planner: {
    reads: ['README.md', 'AGENTS.md', 'docs/README.md', 'ARCHITECTURE.md', 'docs/SYSTEM_INTENT.md', 'docs/PLANS.md', 'docs/CONTEXT_ENGINEERING.md'],
    writes: ['docs/exec-plans/active/', '.agent-context/', 'docs/AGENT_WATCH_LOG.md'],
    outputs: ['execution-plan', 'checkpoint'],
    handoff: 'checkpoint',
    prompt: 'Break requested work into minimal execution steps, route the next canonical docs, and record plan-level handoff state.',
    summary: 'Plans and routes ambiguous work before implementation begins.',
  },
  implementer: {
    reads: ['README.md', 'AGENTS.md', 'docs/README.md', 'ARCHITECTURE.md', 'docs/DESIGN.md', 'docs/ENGINEERING.md', 'docs/PRODUCT_SENSE.md', 'docs/CONTEXT_ENGINEERING.md'],
    writes: ['src/', '.agent-context/', 'docs/AGENT_WATCH_LOG.md'],
    outputs: ['code-change', 'brief'],
    handoff: 'brief',
    prompt: 'Implement scoped changes against the canonical docs, keep edits inside owned paths, and leave a concise resume brief.',
    summary: 'Implements code changes against declared context and ownership boundaries.',
  },
  reviewer: {
    reads: ['README.md', 'AGENTS.md', 'docs/README.md', 'docs/QUALITY_SCORE.md', 'docs/RELIABILITY.md', 'docs/SECURITY.md', 'docs/CONTEXT_EVALUATION.md'],
    writes: ['.agent-context/', 'docs/AGENT_WATCH_LOG.md'],
    outputs: ['review-findings', 'handoff'],
    handoff: 'handoff',
    prompt: 'Review changes for correctness, drift, and boundary violations, then leave a handoff artifact with findings or release status.',
    summary: 'Reviews work for drift, risk, and boundary compliance.',
  },
};

const preset = presets[options.role] ?? presets.implementer;
const manifest = {
  id: options.id,
  name: options.name || options.id.split('-').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' '),
  role: options.role,
  summary: options.summary || preset.summary,
  surfaces: [options.surface],
  reads: preset.reads,
  writes: preset.writes,
  outputs: preset.outputs,
  handoff: preset.handoff,
  prompt: preset.prompt,
  public: true,
};

const dirPath = agentDir(rootDir);
const outputPath = path.join(dirPath, `${options.id}.json`);
if (fs.existsSync(outputPath)) {
  throw new Error(`[agent:new] manifest already exists: ${path.relative(rootDir, outputPath)}`);
}

fs.mkdirSync(dirPath, { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`[agent:new] wrote ${path.relative(rootDir, outputPath)}`);
