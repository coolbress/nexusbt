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
`.github/workflows/ci.yml` and `label.yml` call plinth at one fixed commit, the
pin. Dependabot raises the pin by opening a pull request, which may also raise
other actions. It is merged on green like any other.

**What to run:** in a terminal in this repository:

```bash
gh pr list --author app/dependabot --search coolbress/plinth
```

Merge what it lists with `CONTRIBUTING.md` step 7's command once its checks
pass.

**Done when:** that command lists nothing. That does not prove the pin is the
newest: Dependabot looks once a week and waits three days after a release.
