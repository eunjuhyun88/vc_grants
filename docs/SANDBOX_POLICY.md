# Sandbox Policy

## Sandbox Threat Model

The goal is to reduce accidental damage and invisible privilege expansion during agent execution.

Primary risks:

- writing outside intended repo-local paths
- calling destructive commands without review
- leaking credentials through broad environment access
- treating arbitrary network access as safe by default

## Allowlist Model

Policy lives in `context-kit.json -> sandbox`.

Minimum policy categories:

- `allowReadPaths`
- `allowWritePaths`
- `allowNetworkHosts`
- `denyCommandPrefixes`
- `requireApprovalCommandPrefixes`
- `credentialEnvAllowlist`

The default posture should be:

- broad enough for local repo work
- narrow enough that dangerous actions become visible exceptions

## Network Rules

- local loopback access is usually allowed for preview and harness work
- wildcard hosts should be avoided
- external hosts should be added deliberately, not by default

## Credential Rules

- prefer explicit env allowlists
- do not assume every ambient environment variable is safe for agents
- document secret-bearing integrations before they become normal tool paths

## Destructive Command Rules

At minimum, policy should explicitly deny:

- `rm -rf`
- `git reset --hard`
- `git checkout --`

Push, publish, and deployment commands should usually require explicit approval.

## Mechanical Enforcement

Use:

- `npm run sandbox:check`
- `docs/generated/sandbox-policy-report.md`

The report is not a perfect security proof. It is a visible, reviewable statement of the repo's execution boundary.

