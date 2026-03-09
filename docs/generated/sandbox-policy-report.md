# Sandbox Policy Report

This report summarizes the repo-local sandbox policy used to keep agent execution bounded.

## Policy Summary

- Sandbox enabled: `yes`
- Approval-required prefixes: `git push, npm publish, docker push`
- Credential env allowlist size: `0`

## Checks

- PASS: sandbox.enabled is true
- PASS: allowReadPaths is non-empty
- PASS: allowWritePaths is non-empty
- PASS: allowNetworkHosts is non-empty
- PASS: denyCommandPrefixes is non-empty
- PASS: denyCommandPrefixes includes `rm -rf`
- PASS: denyCommandPrefixes includes `git reset --hard`
- PASS: allowWritePaths does not use wildcard `*`
- PASS: allowNetworkHosts does not use wildcard `*`

## Read Paths

- `README.md`
- `AGENTS.md`
- `ARCHITECTURE.md`
- `context-kit.json`
- `docs/`
- `agents/`
- `tools/`
- `src/`
- `package.json`

## Write Paths

- `.agent-context/`
- `docs/generated/`
- `scripts/dev/`

## Allowed Network Hosts

- `127.0.0.1`
- `localhost`

## Denied Command Prefixes

- `rm -rf`
- `git reset --hard`
- `git checkout --`
- `curl | sh`

