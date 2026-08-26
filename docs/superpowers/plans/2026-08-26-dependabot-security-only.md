# Dependabot Security-Only Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure Dependabot to stop routine npm version-update pull requests while retaining grouped vulnerability remediation for the MSP tenant monitoring frontend.

**Architecture:** Make one policy-only change in `.github/dependabot.yml`: set the routine version-update pull request limit to zero and scope the wildcard dependency group to security updates. Validate both YAML structure and the exact policy values before committing the configuration separately, then open the implementation pull request against `v2`.

**Tech Stack:** Dependabot configuration version 2, YAML, Python 3 with PyYAML, Git, GitHub CLI

## Global Constraints

- Keep `.github/dependabot.yml`; do not create another Dependabot configuration file.
- Keep `package-ecosystem: npm`.
- Keep `directory: /msp-tenant-monitoring/frontend`.
- Keep `schedule.interval: weekly`.
- Set `open-pull-requests-limit: 0`.
- Use one wildcard group named `security-updates` with `applies-to: security-updates` and `patterns: ["*"]`.
- Do not add `target-branch`; Dependabot-generated pull requests must continue to follow the repository default branch, `v2`.
- The implementation pull request must target `v2`.
- Do not modify dependencies, lockfiles, package ecosystems, directories, or schedules.
- Do not reopen, comment on, or otherwise act on closed pull request #154.
- Keep the configuration change in its own commit, separate from the design specification and this plan.

## File Structure

- Modify `.github/dependabot.yml`: define the complete Dependabot security-only update policy for the existing npm frontend scope.
- No test file is added: this repository has no dedicated Dependabot configuration test suite, so validation uses PyYAML plus explicit assertions for every required field.
- No other source, dependency, lock, or configuration file changes.

---

### Task 1: Apply and Validate the Security-Only Dependabot Policy

**Files:**
- Modify: `.github/dependabot.yml:1-12`
- Test: `.github/dependabot.yml` with the inline PyYAML validation command below

**Interfaces:**
- Consumes: Dependabot version 2 configuration schema and the repository default branch setting, `v2`
- Produces: One npm update entry whose routine version-update pull request limit is zero and whose wildcard group applies only to security updates

- [ ] **Step 1: Replace the Dependabot configuration with the approved policy**

Set `.github/dependabot.yml` to exactly:

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

- [ ] **Step 2: Parse the YAML and assert every approved policy value**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

import yaml

path = Path(".github/dependabot.yml")
config = yaml.safe_load(path.read_text())

assert config["version"] == 2
assert len(config["updates"]) == 1

update = config["updates"][0]
assert update["package-ecosystem"] == "npm"
assert update["directory"] == "/msp-tenant-monitoring/frontend"
assert update["schedule"] == {"interval": "weekly"}
assert update["open-pull-requests-limit"] == 0
assert "target-branch" not in update
assert update["groups"] == {
    "security-updates": {
        "applies-to": "security-updates",
        "patterns": ["*"],
    }
}

print("Dependabot security-only policy validated")
PY
```

Expected: exit code `0` and `Dependabot security-only policy validated`.

- [ ] **Step 3: Review formatting and confirm the diff contains only the approved changes**

Run:

```bash
git diff --check
git --no-pager diff -- .github/dependabot.yml
```

Expected: `git diff --check` exits `0`. The diff changes
`open-pull-requests-limit` from `1` to `0`, renames
`frontend-dependencies` to `security-updates`, and adds
`applies-to: security-updates`. It retains the npm ecosystem, frontend
directory, weekly schedule, and wildcard pattern, and does not add
`target-branch`.

- [ ] **Step 4: Guard the implementation commit scope**

Run:

```bash
test "$(git status --short)" = " M .github/dependabot.yml"
```

Expected: exit code `0`. If it fails, inspect `git status --short` and keep
unrelated files out of the implementation commit.

- [ ] **Step 5: Commit only the Dependabot configuration change**

Run:

```bash
git add -- .github/dependabot.yml
git diff --cached --check
git commit -m "fix(dependabot): allow only security updates"
```

Expected: one new commit containing only `.github/dependabot.yml`.

- [ ] **Step 6: Verify the committed configuration**

Run:

```bash
test "$(git diff-tree --no-commit-id --name-only -r HEAD)" = ".github/dependabot.yml"
git status --short
git --no-pager show --stat --oneline HEAD
```

Expected: the path assertion exits `0`, `git status --short` prints nothing,
and the commit summary lists only `.github/dependabot.yml`.

---

### Task 2: Open the Implementation Pull Request Against `v2`

**Files:**
- Modify: none
- Test: branch diff and GitHub pull request metadata

**Interfaces:**
- Consumes: the committed design specification, implementation plan, and security-only Dependabot configuration
- Produces: one open GitHub pull request from the current branch into `v2`

- [ ] **Step 1: Verify the complete branch scope before publishing**

Run:

```bash
git fetch origin v2
git diff --check origin/v2...HEAD
git --no-pager diff --name-only origin/v2...HEAD
git --no-pager log --oneline origin/v2..HEAD
```

Expected: `git diff --check` exits `0`; the changed-file list contains exactly:

```text
.github/dependabot.yml
docs/superpowers/plans/2026-08-26-dependabot-security-only.md
docs/superpowers/specs/2026-08-26-dependabot-security-only-design.md
```

The commit log contains separate commits for the design specification, this
implementation plan, and the Dependabot configuration change. No dependency or
lockfile appears in the diff.

- [ ] **Step 2: Push the current implementation branch**

Run:

```bash
git push -u origin "$(git branch --show-current)"
```

Expected: the current branch is pushed successfully and tracks its matching
remote branch.

- [ ] **Step 3: Create the pull request with `v2` as the explicit base**

Run:

```bash
gh pr create \
  --base v2 \
  --head "$(git branch --show-current)" \
  --title "Restrict Dependabot to security updates" \
  --body-file - <<'EOF'
## Summary

- disable routine npm version-update pull requests
- group all supported npm vulnerability remediations
- retain the existing frontend scope and weekly schedule

## Validation

- parsed `.github/dependabot.yml` with PyYAML
- asserted the complete security-only policy
- reviewed the branch diff against `v2`

Closed PR #154 requires no action.
EOF
```

Expected: `gh pr create` returns the URL of a new pull request. Do not use any
command that reopens, comments on, or edits closed pull request #154.

- [ ] **Step 4: Verify the pull request target and state**

Run:

```bash
gh pr view --json baseRefName,headRefName,state,title,url \
  --jq '{base: .baseRefName, head: .headRefName, state, title, url}'
```

Expected: `base` is `v2`, `head` is the current implementation branch, `state`
is `OPEN`, and the title is `Restrict Dependabot to security updates`.
