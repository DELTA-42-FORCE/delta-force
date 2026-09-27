---
name: delta-force-development
description: Use when implementing, reviewing, or coordinating Delta Force CRM work in this repository, especially the no-PR integration flow for develop.
---

# Delta Force CRM development workflow

Follow the repository's current product and engineering decisions in `AGENTS.md`, `docs/`, the linked GitHub issue, and the GitHub Project. This skill details issue ownership, preflight checks, and the direct-to-`develop` flow; it does not grant permission to bypass checks or change repository settings.

## Before choosing or changing work

1. Preserve the developer's existing work. Check `git status`; do not reset, discard, or overwrite unrelated modifications. If the worktree is dirty, use an isolated worktree or ask before touching overlapping files.
2. Fetch GitHub state and `origin/develop`. Read the relevant requirements/ADR, issue acceptance criteria, dependencies, and current Project status. Do not start an issue already assigned or claimed; coordinate first.
3. Perform a read-only preflight on current `develop`: run `just check`, review the latest full-repository/security audit evidence, inspect recent commits and changes since that evidence, and inspect code relevant to the candidate work. Run `just audit` when due, when dependencies/security-sensitive paths changed, or before dependency changes. Do not claim a scan is exhaustive if tools or environment did not cover a surface.
4. Report findings with file/line evidence, impact, confidence, and a concise correction plan. Stop and correct confirmed critical/security/data-loss findings or reproducible blockers before selecting unrelated work. Record other out-of-scope findings as proposed follow-ups; do not silently broaden a task or create GitHub issues without authorization.
5. Select only an issue marked **Ready** whose dependencies are satisfied. If no suitable issue exists, report that rather than inventing scope.

## Claim and implement

1. Claim the issue before coding: assign it to the developer responsible, set its Project status to **In progress**, and comment with owner, branch name, start date, starting `develop` SHA, and preflight evidence/findings. This comment is the shared handoff for the next agent. If GitHub write access is unavailable, ask the user to claim it; do not proceed as if the claim succeeded.
2. Create a short branch from the fetched `origin/develop`: `feature/<issue>-<summary>`, `fix/<issue>-<summary>`, or `chore/<issue>-<summary>`. Keep the change focused on one issue.
3. Implement its acceptance criteria, using synthetic data. Add risk-appropriate tests and update docs/contracts when behavior or decisions change. Treat repository-wide defects as separate work unless they block this issue.
4. Review your own diff for scope, authorization, privacy, auditability, migrations, tests, and accidental secrets. Run `just check`; run the applicable manual/Windows tests. Never declare a Windows desktop change ready without the required Windows CI job. Changes under `apps/desktop` also require another teammate's approval recorded on the issue before integration.

## Integrate into `develop` without a PR

1. Push the working branch to origin to run GitHub Actions. Wait until every **required** status check for the exact branch-head commit is green; the optional legacy PostgreSQL job is not a substitute for the required SQLite check. Do not integrate while a required check is pending or failing.
2. Fetch `origin/develop`. If it advanced, rebase the work branch onto it, rerun `just check`, push the new branch head, and wait for checks on that new commit. Never force-push; if a normal push is rejected, fetch and coordinate.
3. Confirm `origin/develop` is an ancestor of the tested branch head. Integrate only that same tested commit by fast-forward, with a normal non-force push such as `git push origin HEAD:develop`. Do not create an untested merge commit, bypass branch protection, or push to `main`.
4. Verify that `origin/develop` now points to the integrated commit and that its push-triggered workflow is green. If GitHub rejects the push or a check regresses, stop and fix/retest; never disable or bypass a required check.
5. Update the issue/Project to **Done** and close the issue only when acceptance criteria are met. Comment with the commit SHA, summary, checks, and any remaining limitations. Update `docs/CONTINUATION.md` for meaningful project-wide state/decisions, not for every trivial edit.

## Boundaries

- Normal work does not use a PR to `develop`; releases and hotfixes to `main` still require a PR, independent approval, and required checks.
- An explicit request to implement a selected issue authorizes the commits, working-branch push, issue claim/status updates, and a checked fast-forward to `develop` described above. It does not authorize force pushes, direct pushes to `main`, branch-protection bypass, permission changes, production operations, or unrelated GitHub issues.
- Keep `main` protections intact. Do not change branch rulesets/protection unless the user explicitly asks.
- Preserve client data, secrets, the Windows sidecar/icon invariants, and all rules in `AGENTS.md`.
