# Keep this project current

Improvements reach this project three ways. Do them in this order, because the
first decides what the second can bring. None of them happens by itself: this
project turns on no automatic update for plinth.

When the template is behind, a monthly issue in this repository lists the same
steps.

## 1. Update plinth on your computer

**What it brings:** plinth's newest commands, and the template version step 2
moves to. With an old plinth, step 2 can find nothing to do while a newer
template is out.

**What to run:** in a terminal:

```bash
claude plugin marketplace update plinth
claude plugin update plinth@plinth
```

When the [release note](https://github.com/coolbress/plinth/releases) names
another command, such as `claude plugin update <name>@plinth`, run it too. Then
type `/reload-plugins` in Claude Code, or start a new session.

Do not turn on automatic updates from inside this project. In Claude Code,
`/plugin`, then Marketplaces, plinth, Enable auto-update, chosen in a session
in this repository, rewrites this project's committed `.claude/settings.json`.
To have new versions of plinth arrive by themselves, make that choice in a
session started outside any project.

**Done when:** `claude plugin list` shows `plinth@plinth` at the version on top
of <https://github.com/coolbress/plinth/releases>.

## 2. Update the template

**What it brings:** the newest version of the files this project started with:
its CI, documents and agent settings.

**What to run:** in Claude Code in this repository:

```text
/plinth:template-update
```

It shows its plan and asks before it writes anything, then opens a draft pull
request. When a file conflicts with this project's own changes, it recommends a
side and applies it on your word. Mark the pull request ready and merge it with
`CONTRIBUTING.md` step 7's command once its checks pass.

**Done when:** `_commit` in `.copier-answers.yml` on `main` names the new
version, and `/plinth:template-update` says there is nothing to update.

## 3. Merge the plinth pin pull request

**What it brings:** changes to plinth's checks.
`.github/workflows/ci.yml` and `label.yml` call plinth
at one fixed commit, the pin. Dependabot raises the pin by opening a pull request, which may also raise
other actions. It is merged on green like any other.

**What to run:** in a terminal in this repository:

```bash
gh pr list --author app/dependabot --search coolbress/plinth
```

Merge what it lists with `CONTRIBUTING.md` step 7's command once its checks
pass.

**Done when:** that command lists nothing. That does not prove the pin is the
newest: Dependabot looks once a week and waits three days after a release.

## Other dependency pull requests

Dependabot also raises this project's packages each week, as
`.github/dependabot.yml` says: development tools in one pull request, runtime
minors and patches in another, a runtime major alone. Take them one pull
request at a time, and merge each on green with `CONTRIBUTING.md` step 7's
command.

**When one stays red:** read why in the failing check's log first. When one
package in a group is the cause, for example a new version that changes files
this project commits, take it out of the group with `exclude-patterns` and
merge the rest of the group on green. In `.github/dependabot.yml`, under that
group:

```yaml
      runtime-minor:
        dependency-type: "production"
        update-types: ["minor", "patch"]
        exclude-patterns: ["<name>"]
```

Dependabot then opens the group without it, and that package in a pull request
of its own, which waits until this project is ready for it. Or fix this project
on the Dependabot branch (regenerate those files) and push: from then on
Dependabot no longer rebases that branch, and `@dependabot recreate` would
replace the pushed commits, so keeping it current is yours.

A comment `@dependabot ignore <name>` on a group's pull request (on a pull
request of one package, `@dependabot ignore this dependency`) closes it and
stops updates of that package in this repository until
`@dependabot unignore <name>`.
It is a lasting pin, the silent ageing `dependabot.yml` exists to prevent, not
a way past one red run.

**Yours to change:** `.github/dependabot.yml`'s groups and cooldown are this
project's to change. `/plinth:floor-check` checks only that the file exists,
and `/plinth:template-update` keeps this project's lines unless the template
changed the same ones, which it then shows as a conflict.

## Before saying plinth lacks something

This project calls plinth at one fixed commit, the pin, which can be many
releases behind. A feature missing from plinth's files at the pin may already
be released. Before saying plinth does not do something, or asking plinth for
it, read the latest release's notes: plinth's
[`CHANGELOG.md` on `main`](https://github.com/coolbress/plinth/blob/main/CHANGELOG.md),
where the first section after `[Unreleased]` is the latest release, or
<https://github.com/coolbress/plinth/releases>. Not plinth's code on `main`:
work not yet released does not reach this project.

To see which version this project calls, take the commit from the `coolbress/plinth` `uses:` line in `.github/workflows/ci.yml`, after `@`, and look it up among plinth's tags:

```bash
git ls-remote --tags https://github.com/coolbress/plinth | grep <commit>
```

It prints the version as `refs/tags/vX.Y.Z^{}`; when it prints nothing, the
pin is not a release. The release sections above that version, not
`[Unreleased]`, are what this project does not have yet.

When the feature is in one of them, the answer is raising the pin, not a
request to plinth: step 3 above. Its pull request moves `ci.yml` and `label.yml` together. When
Dependabot has not opened one yet, put the latest release's commit, the one
`git ls-remote https://github.com/coolbress/plinth 'refs/tags/<tag>^{}'`
prints, in every `coolbress/plinth` `uses:` line, in one pull request.
