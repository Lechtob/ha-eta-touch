# Repository settings

GitHub repository settings are not versioned with the source code. Keep this checklist in sync
with the active settings for `Lechtob/ha-eta-touch`.

## General

- Default branch: `main`
- Enable issues and private vulnerability reporting.
- Enable merge commits and squash merging.
- Disable rebase merging.
- Enable automatic head branch deletion.
- Enable auto-merge and always suggest updating pull request branches.

Merge feature and maintenance pull requests into `develop` with squash merge. Merge release
pull requests from `develop` into `main` with a merge commit so both GitFlow branches retain
shared ancestry.

## Ruleset: main

Target the `main` branch and enable the ruleset.

- Restrict deletions.
- Block force pushes.
- Require a pull request before merging.
- Required approvals: `0` while the project has only one maintainer.
- Require conversation resolution before merging.
- Require status checks to pass:
  - `CI`
  - `HACS`
  - `Hassfest`
- Require branches to be up to date before merging.

Do not require linear history on `main`; release pull requests use merge commits by design.
Do not enable required code-owner approval until another active maintainer can review changes.

## Ruleset: develop

Target the `develop` branch and enable the ruleset.

- Restrict deletions.
- Block force pushes.
- Require a pull request before merging.
- Required approvals: `0` while the project has only one maintainer.
- Require conversation resolution before merging.
- Require status checks to pass:
  - `CI`
  - `HACS`
  - `Hassfest`
- Require branches to be up to date before merging.

Feature branches should normally be squash merged into `develop`.

## Ruleset: release tags

Create a tag ruleset targeting `v*`.

- Restrict tag updates.
- Restrict tag deletions.
- Allow maintainers to create new release tags.

## Security and automation

- Enable the dependency graph.
- Enable Dependabot alerts and security updates.
- Enable secret scanning and push protection when available.
- Keep Actions permissions at read-only by default.
- Do not allow Actions to create or approve pull requests unless a future workflow requires it.
