# Dependabot Security-Only Updates Design

**Status:** Approved

## Context

The repository currently configures Dependabot version updates for the npm
project in `/msp-tenant-monitoring/frontend`. The weekly schedule and wildcard
dependency group allow Dependabot to open routine version-update pull requests,
with one such pull request permitted at a time.

The desired behavior is to stop routine dependency version-update pull requests
while preserving Dependabot vulnerability remediation for the same frontend
project.

## Goals

- Retain the existing Dependabot configuration file and npm update scope.
- Prevent Dependabot from opening routine version-update pull requests.
- Continue allowing Dependabot security-update pull requests for all npm
  dependencies in the configured frontend directory.
- Keep security updates grouped in a single pull request when Dependabot can
  group them.
- Target pull requests at the repository default branch, `v2`.

## Non-Goals

- Changing dependencies or lockfiles.
- Changing the npm project directory or update schedule.
- Adding another package ecosystem or directory.
- Creating, reopening, or otherwise acting on closed pull request #154.
- Defining an implementation sequence; that belongs in a later implementation
  plan.

## Configuration Design

Keep `.github/dependabot.yml` and preserve these existing values:

- `package-ecosystem: npm`
- `directory: /msp-tenant-monitoring/frontend`
- `schedule.interval: weekly`

Change `open-pull-requests-limit` from `1` to `0`. Dependabot interprets this
limit as applying to version-update pull requests, so setting it to zero
disables routine version-update pull requests without disabling security
updates.

The resulting configuration is:

```yaml
version: 2
updates:
  - package-ecosystem: npm
    directory: /msp-tenant-monitoring/frontend
    schedule:
      interval: weekly
    open-pull-requests-limit: 0
    groups:
      security-updates:
        applies-to: security-updates
        patterns:
          - "*"
```

The group name communicates its purpose. `applies-to: security-updates`
restricts the wildcard group to vulnerability remediation, and `patterns:
["*"]` includes every npm dependency in the configured directory.

No `target-branch` setting is required because Dependabot targets the
repository default branch. Dependabot-generated pull requests will therefore
target `v2`, which is the default branch for this repository. The later
implementation pull request that changes this configuration must also target
`v2`.

## Resulting Behavior

Dependabot will not open routine version-update pull requests because their
open pull request limit is zero. The weekly schedule remains configured for
version-update checks but cannot produce routine pull requests while that limit
is zero. Security updates are vulnerability-driven, remain exempt from the
version-update limit, and are eligible for the security-only wildcard group.
Dependabot will continue to evaluate vulnerability alerts and open grouped
security-update pull requests against `v2` when remediation is available.

Closed pull request #154 is historical and requires no migration or cleanup.

## Validation

Review the resulting YAML to confirm:

1. It remains valid Dependabot version 2 configuration.
2. The npm ecosystem, frontend directory, and weekly schedule are unchanged.
3. `open-pull-requests-limit` is exactly `0`.
4. The wildcard group contains `applies-to: security-updates`.
5. No explicit target branch overrides the repository default branch, `v2`.
6. No files other than `.github/dependabot.yml` are changed during
   implementation.
7. The later implementation pull request targets `v2`.

After the configuration reaches `v2`, repository maintainers can confirm that
routine version-update pull requests are no longer created while future
vulnerability alerts can still produce grouped security-update pull requests.

## Risks and Mitigations

- **Routine upgrades stop entirely:** This is intentional. Future non-security
  upgrades must be initiated manually or through a separately approved policy.
- **Security updates may not always group:** Dependabot can separate updates
  when dependency compatibility or advisory constraints prevent grouping.
  Security remediation remains enabled even when a single grouped pull request
  is not possible.
- **Default branch changes later:** Dependabot follows the repository default
  branch because no explicit target is configured. If the default changes,
  maintainers must decide whether Dependabot should follow it or explicitly
  remain on `v2`.

## Acceptance Criteria

- The approved implementation changes only `.github/dependabot.yml`.
- Routine npm version-update pull requests are disabled with
  `open-pull-requests-limit: 0`.
- All npm vulnerability remediations remain covered by a wildcard group scoped
  with `applies-to: security-updates`.
- The npm ecosystem, `/msp-tenant-monitoring/frontend` directory, and weekly
  schedule remain unchanged.
- Dependabot-generated pull requests and the later implementation pull request
  target `v2`.
- Closed pull request #154 receives no action.
