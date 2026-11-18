# Undo a merged change

A change that is already on `main` is undone by a new pull request that takes
it back out. It goes through the same checks as any other, so the way back is
as safe as the way in. `main`'s history is never rewritten: it is protected,
and a force push is denied.

## 1. Open the revert

On the merged pull request's page, press **Revert**, or run this in a
terminal in this repository, with the pull request's number for `<n>`:

```bash
gh pr revert <n>
```

(gh 2.83.0 or newer; `gh --version` says which you have.) Either opens a new
pull request, on a new branch, that undoes the change.

Keep the title GitHub writes, `Revert "<title>"`: `ci / pr-title` passes it
when the title inside the quotes passes on its own. The revert made by hand,
under [When the revert conflicts](#when-the-revert-conflicts), is titled
`revert: <what the change did>` instead, with the type `revert` written out,
because the title git writes there ends in `(#<n>)`, which the check
refuses. Both are this project's titles; the one GitHub
writes needs no edit.

A revert takes the same review as any change: the default review in
`AGENTS.md`, a fresh-context review given the revert's diff, run before the
description is written so its findings go in it. It is short, since the diff
should be the reverted change turned around and nothing else. When the
change does harm now and no one can review in time, merge without it and
say so on the line, `Review: none (<reason>)`; the line is never left out.

Then fill the description before anything else. GitHub writes only
`Reverts <owner>/<repo>#<n>`, and the description becomes the squash
commit on `main`, which cannot be fixed afterwards. Start from the project's
form, `.github/PULL_REQUEST_TEMPLATE.md`: write `Reverts #<n>.` and why
under `What and why`, fill `What I checked myself`, write a
`Not verified:` line (`Not verified: nothing` when that is true), fill the
`Review:` line with the review that ran, put `Related to #<m>` for an issue
the reverted change closed and the `Assisted-by` trailers last, and delete
the comment lines. Edit the description on the pull request's page, or write it to
a file outside the checkout and run `gh pr edit <n> --body-file <file>`, with
the revert's number for `<n>`. The edit runs `ci / pr-title` again.

## 2. Merge it

The checks run as for any change and take about as long.
`gh pr checks <n> --watch` with the revert's number for `<n>` returns when
they finish. A `not yet confirmed` line in `ci / pr-title` is a warning, not
a failure, and is shown on the run's summary page: read it, since it names a
description field that is missing.

Merge it like any other pull request, with `CONTRIBUTING.md` step 7's command,
once its checks pass. The `<n>` there is the revert's number and
the `<sha>` is the revert's head commit, the one the description was read
against: `gh pr view <n> --json headRefOid --jq .headRefOid` prints it.
Whatever a merge sets off, such as a deploy, runs again for the revert.

## 3. After the merge

An issue the reverted change closed is not done any more. Reopen it
(`gh issue reopen <m>`) and add to its `## Outcome` that the change was
reverted, by which pull request, and why; untick the criteria it no longer
meets.

Then confirm `main` is back. With the reverted change's merged commit for
`<merged commit>`:

```bash
git fetch origin
git diff --stat <merged commit>~1 origin/main -- $(git diff --name-only <merged commit>~1 <merged commit>)
```

It prints nothing when every file the change touched is as it was before
the change. A file it names was also changed by a later change, which the
revert keeps; read that diff to see that only the later change's lines
remain.

## When the revert conflicts

When a later change touched the same lines, GitHub cannot make
the revert and says so, and `gh pr revert` fails.
Make it on a branch instead, or ask the agent to:

```bash
git fetch origin
git switch -c revert/<n> --no-track origin/main
git revert <merged commit>
```

The merged commit is the one the pull request landed as; its page names it. git
stops at each file it cannot settle: keep what the later change needs, then
`git add` the file and run `git revert --continue`. Push the branch and open
the pull request:

```bash
git push origin revert/<n>
gh pr create --title 'revert: <what the change did>'
```

The title is passed because the one git writes, `Revert "<title> (#<n>)"`,
fails `ci / pr-title`, which refuses a quoted title that ends in `(#N)`.
`gh pr create` asks which form to start from: choose the pull request form
(`CONTRIBUTING.md` step 5 says which one applies). Write `Reverts #<n>.` under
`What and why`, fill `What I checked myself` and the `Review:` line, and delete
the comment lines. An agent has no terminal for that question, and gh refuses
without one: it writes the form's fields into the description itself.

## What a revert does not undo

A revert undoes the code, not what the code already did: rows it wrote or
deleted, a release already published, a message already sent stay as they
are. A change that carried a database migration is not undone by reverting
its code alone. The database keeps the new shape while the code goes back to
expecting the old one, and the old code can fail against it.

This project started without a database; if it has one now, read how its
backups come back before reverting such a change.
