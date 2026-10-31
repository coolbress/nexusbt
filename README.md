# nexusbt

> One line saying what this is.

## Getting started

```bash
git clone <this repository>
cd nexusbt
uv sync --locked   # 1. dependencies, the same command CI runs; the lockfile is used as is
uv run pytest      # 2. tests
```

## Developing

```bash
uv run ruff check . && uv run ruff format .   # lint and format
uv run mypy .                                  # types
uv run pytest                                  # tests
uv build                                       # build
```

CI runs each of these as a separate check, plus a secret scan and CodeQL.
Pass them locally first. The list of required checks is the repository's
ruleset, so it is not repeated here.

## Releasing

A version tag (`v0.1.0`) publishes this package to PyPI and makes a GitHub
Release, through [`.github/workflows/release.yml`](.github/workflows/release.yml).
No password or token is stored: PyPI trusts the workflow itself. Three
things are set up once, by a person, in a web browser before the first tag;
the steps, in plain words, are in
[`docs/how-to/publish-a-release.md`](docs/how-to/publish-a-release.md).

## Working with Claude Code

`.claude/settings.json` turns on the `Beginner or non-engineer` output style
for everyone who opens this repository in Claude Code. The agent does the same
engineering work and explains it for a beginner engineer or a non-engineer:
every change ends with what changed, why, and what to look at next; a merge,
a template update or a failure gets a report of what shows it and what is
still unknown; every decision comes with one recommended option. The text is
in [`.claude/output-styles/`](.claude/output-styles/).

To turn it off for yourself, type `/output-style default` in Claude Code. It
writes this to `.claude/settings.local.json`, which is yours alone and never
committed; writing it by hand does the same from the next session:

```json
{
  "outputStyle": "default"
}
```

Delete that line to have the style again.

A choice in your own `~/.claude/settings.json` does not turn it off: the
project's setting takes precedence over it.

`skillListingBudgetFraction` gives the list of skills the agent can pick from
1.5% of the model's context instead of 1%. On a model with 200k tokens of
context, 1% shortened some skill descriptions to about their name, so the
agent could not tell when to use them; at 1.5% none were shortened, and the
list grew by about 200 tokens in every session. On a 1M model nothing
changed.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md), in particular the test policy. `main` is
protected; a change lands as a pull request with green checks.

## About this repository

Created from [`coolbress/plinth-template`](https://github.com/coolbress/plinth-template).
The CI checks come from [`coolbress/plinth`](https://github.com/coolbress/plinth).

## First day

- If the merge stays blocked on CodeQL, push once more: `git commit --allow-empty -m 'ci: trigger code scanning' && git push`.
- If your everyday gh token is fine-grained with selected repositories, add `nexusbt` to it: https://github.com/settings/personal-access-tokens
- Dependabot opens pull requests from the first minute: merge one when every required check is green, or close it. CodeQL does not analyse a head Dependabot pushed; `ci / deps` and the tests run on it, and `main` is analysed after the merge. Its first one usually lands while the door waits for CodeQL, so the door's own pull request is #2. After "Update branch" the merge stays blocked for a minute or two while the required checks and CodeQL run on the new head, and a merge tried then is refused with "the base branch policy prohibits the merge": wait for the state to read clean rather than adding an approval, which a person's own branch update did not need.

Made with [plinth](https://github.com/coolbress/plinth).
