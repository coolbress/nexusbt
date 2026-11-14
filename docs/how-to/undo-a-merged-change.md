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

## 2. Merge it

Merge it like any other pull request, with `CONTRIBUTING.md` step 7's command,
once its checks pass. Whatever a merge sets off, such as a deploy, runs again
for the revert.

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
