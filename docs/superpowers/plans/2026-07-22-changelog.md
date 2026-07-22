# Changelog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a curated, user-facing changelog with an Unreleased section and a retrospective 0.2.1 release entry.

**Architecture:** Keep release history in one root-level Markdown file maintained manually from Conventional Commit history. Use Keep a Changelog categories, ISO release dates, and commit-based GitHub comparison links because the repository currently has no version tags.

**Tech Stack:** Markdown, Git, Keep a Changelog conventions

## Global Constraints

- Write the changelog in English.
- Describe user-visible outcomes rather than copying commit subjects.
- Include only categories that contain entries.
- Document `0.2.1` as the first retrospective release; do not reconstruct `0.2.0`.
- Keep the design-only subagent completion sound change out of the changelog.
- Do not modify `VERSION`; this task documents the current `0.2.1` state.

---

### Task 1: Add the curated changelog

**Files:**
- Create: `CHANGELOG.md`
- Reference: `docs/superpowers/specs/2026-07-22-changelog-design.md`
- Track: `docs/superpowers/plans/2026-07-22-changelog.md`

**Interfaces:**
- Consumes: Git history ending release `0.2.1` at commit `a44e0da` and subsequent changes through `HEAD`
- Produces: A manually maintained `CHANGELOG.md` for users and future release workflows

- [ ] **Step 1: Verify release boundaries and current unreleased commits**

Run:

```bash
git show --no-patch --format='%h %cs %s%n%b' a44e0da
git log --reverse --format='%h %cs %s' a44e0da..HEAD
```

Expected: the release commit reports `release: 0.2.1` dated `2026-07-01`; later commits include the updater repository-slug fix, provider usage monitoring, its documentation/archive commits, the design-only sound spec, and the live Codex usage fix.

- [ ] **Step 2: Create the changelog with curated entries**

Create `CHANGELOG.md` with exactly this initial content:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Display provider usage limits for Claude and Codex in the widget.
- Read live Codex usage limits from local session data.

### Fixed

- Use the canonical GitHub repository address for update checks and self-updates.

## [0.2.1] - 2026-07-01

### Fixed

- Keep the widget reliably above other windows on GNOME/Mutter.

### Removed

- Remove the widget toggle command and launcher in favor of the explicit start and stop helpers.

[Unreleased]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/a44e0da...HEAD
[0.2.1]: https://github.com/dmitrykostenkoweb/ai-status-monitor/compare/c2e15ae...a44e0da
```

- [ ] **Step 3: Verify the changelog against the approved design**

Run:

```bash
sed -n '1,220p' CHANGELOG.md
rg -n 'SubagentStop|completion sound|0\.2\.0' CHANGELOG.md
git diff --check
```

Expected: the rendered source contains the agreed Unreleased and 0.2.1 sections; `rg` exits with status 1 and prints no excluded entries; `git diff --check` exits with status 0 and prints nothing.

- [ ] **Step 4: Review the final documentation diff**

Run:

```bash
sed -n '1,220p' CHANGELOG.md
sed -n '1,280p' docs/superpowers/plans/2026-07-22-changelog.md
git status --short
```

Expected: both new documents contain the agreed content; status lists only the
new changelog and implementation plan, while the already committed design is
not modified.

- [ ] **Step 5: Commit the documentation**

Run:

```bash
git add CHANGELOG.md docs/superpowers/plans/2026-07-22-changelog.md
git commit -m "docs: add project changelog"
git show --stat --oneline --summary HEAD
```

Expected: one focused commit named `docs: add project changelog` containing the new changelog and its implementation plan.
