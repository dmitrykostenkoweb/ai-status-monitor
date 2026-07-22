# Changelog Design

## Goal

Add a user-facing changelog that records released behavior and keeps upcoming
changes visible without duplicating the raw Git history.

## Format

Create a root-level `CHANGELOG.md` in English, following the structure from
Keep a Changelog:

- begin with an `[Unreleased]` section;
- group entries under `Added`, `Changed`, `Fixed`, and `Removed` only when a
  category has content;
- describe user-visible outcomes rather than commit implementation details;
- use ISO dates for released versions;
- add GitHub comparison links for `Unreleased` and each documented release.

The changelog is maintained manually. Conventional Commit subjects remain the
source material, but they are curated rather than copied verbatim.

## Initial Content

### Unreleased

Document changes made after release commit `a44e0da`:

- provider usage-limit monitoring for Claude and Codex;
- live Codex usage values derived from local session data;
- the corrected canonical GitHub repository slug used by the updater.

The design-only subagent completion sound commit is not user-visible shipped
behavior and must not appear in the changelog.

### 0.2.1 - 2026-07-01

Document the two changes included in this release:

- reliably keeping the widget above other windows on GNOME/Mutter;
- removing the widget toggle command and launcher in favor of the explicit
  start and stop helpers.

Do not reconstruct a `0.2.0` entry in this change. Version `0.2.1` is the first
retrospective release entry, as agreed.

## Release Workflow

For a future release:

1. Move applicable entries from `[Unreleased]` into a new version section.
2. Add the release date in ISO format.
3. Update the comparison links.
4. Bump `VERSION` in the same release workflow.

Empty categories are omitted. Migration instructions or security notices are
added only when a release actually requires them.

## Verification

Review the final Markdown rendering, verify every initial entry against the Git
history around `a44e0da`, and run `git diff --check`. No runtime tests are
needed because this change only adds documentation.
