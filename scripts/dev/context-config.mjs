#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const configPath = path.join(rootDir, 'context-kit.json');

function loadConfig() {
  if (!fs.existsSync(configPath)) return {};
  return JSON.parse(fs.readFileSync(configPath, 'utf8'));
}

function getAtPath(object, dottedPath) {
  if (!dottedPath) return object;
  return dottedPath.split('.').reduce((current, key) => {
    if (current == null) return undefined;
    return current[key];
  }, object);
}

function usage() {
  process.stderr.write('Usage: node scripts/dev/context-config.mjs <get|get-string|get-json> <path>\n');
}

const [command, dottedPath] = process.argv.slice(2);
if (!command) {
  usage();
  process.exit(1);
}

const config = loadConfig();
const value = getAtPath(config, dottedPath);

if (command === 'get' || command === 'get-string') {
  if (value == null) process.exit(0);
  process.stdout.write(typeof value === 'string' ? value : String(value));
  process.exit(0);
}

if (command === 'get-json') {
  process.stdout.write(JSON.stringify(value ?? null));
  process.exit(0);
}

usage();
process.exit(1);
