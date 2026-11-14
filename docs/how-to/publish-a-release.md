# Publish a release to PyPI

PyPI is the public shelf Python packages are installed from: once this
project is there, anyone can run `pip install nexusbt` or
`uv add nexusbt`. This page is the steps, in order, for the first
release and every one after it.

How it works, in one paragraph: you push a version tag, such as `v0.1.0`.
The workflow `.github/workflows/release.yml` then checks the tag, builds the
package, uploads it to PyPI and makes a release page on GitHub. No password
or token is stored anywhere: PyPI is told once, by you, to trust this
repository's workflow (that is "Trusted Publishing"), and from then on it
accepts uploads from that workflow and nothing else.

Steps 1 to 3 are done once, by you, in a web browser. The agent cannot do
them: they are your accounts. Never paste a password, a recovery code or a
token into the chat.

## 1. Make a PyPI account with two-factor authentication

1. Open <https://pypi.org/account/register/> and create an account.
2. PyPI sends an email; open the link in it to confirm your address.
3. PyPI asks you to turn on two-factor authentication (2FA) before you can do
   anything else. 2FA means a second proof besides the password: a code from
   an authenticator app on your phone, or a security key. Follow the page.
4. PyPI shows recovery codes. Keep them somewhere safe, offline: they are the
   only way back in if you lose your phone.

**Try it first on TestPyPI (recommended).** TestPyPI
(<https://test.pypi.org>) is a practice copy of PyPI: what you publish there
does not appear on the real shelf. It has its own accounts, so repeat the
four steps above at <https://test.pypi.org/account/register/>. Step 4 below
says how to send a release there instead of PyPI.

## 2. Tell PyPI to trust this repository (a "pending publisher")

The project does not exist on PyPI yet, so you register a *pending*
publisher: a promise that the first upload from this workflow may create it.

1. Check the name is free: open <https://pypi.org/project/nexusbt/>.
   "Not Found" means it is free. If a project is already there, choose
   another name, change `name` in `pyproject.toml` in a pull request, and use
   that name below.
2. Open <https://pypi.org/manage/account/publishing/> (for the practice run,
   <https://test.pypi.org/manage/account/publishing/>).
3. Under "Add a new pending publisher", choose **GitHub** and fill in:

   | Field | What to type |
   |---|---|
   | PyPI Project Name | `nexusbt` |
   | Owner | `coolbress` |
   | Repository name | `nexusbt` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. Press **Add**.

Each field must match exactly. If one differs, PyPI refuses the upload and
the run fails with `invalid-publisher` (see "When a release fails").

A pending publisher does not reserve the name: until the first upload,
someone else can still take it.

## 3. Make the `pypi` environment on GitHub

The workflow uploads from a GitHub *environment* named `pypi`. It is where
you decide who may let a release out.

1. On GitHub, open this repository, then **Settings** > **Environments** >
   **New environment**.
2. Name it `pypi` and press **Configure environment**.
3. Recommended, both on the same page:
   - **Required reviewers**: tick it and add yourself. Each release then
     waits for you to press **Approve** before anything is uploaded.
   - **Deployment branches and tags**: choose **Selected branches and
     tags**, press **Add deployment branch or tag rule**, choose **Tag**,
     and type `v*`. Only a version tag can then use this environment.
4. Press **Save protection rules**.

Do not add a secret here: Trusted Publishing needs none.

## 4. Publish

1. Set the version. The version is written in `pyproject.toml`
   (`version = "0.1.0"` to start). For a new release, ask the agent to raise
   it in a pull request, for example "raise the version to 0.2.0 with
   `uv version 0.2.0`", and add what changed to `CHANGELOG.md`. Merge it when
   its checks are green.
2. For the practice run on TestPyPI only: **Settings** > **Secrets and
   variables** > **Actions** > **Variables** > **New repository variable**,
   name `PYPI_REPOSITORY_URL`, value `https://test.pypi.org/legacy/`. Delete
   the variable afterwards; without it the workflow publishes to PyPI.
3. Push the tag. The tag is the version with a `v` in front, on the merged
   `main`. In a terminal, in this repository:

   ```bash
   git fetch origin
   git tag v0.2.0 origin/main
   git push origin v0.2.0
   ```

   You push the tag yourself, not the agent: a version on PyPI cannot be
   replaced, so letting it out is a person's decision.
4. Open the repository's **Actions** tab and the run named **Release**. If
   you set required reviewers, press **Review deployments**, tick `pypi` and
   **Approve and deploy**.
5. When the run is green: the package is at
   `https://pypi.org/project/nexusbt/` (or `test.pypi.org`), and a
   release page with its notes is under **Releases** on GitHub. On PyPI,
   open the file under **Download files** and **View details**: the
   provenance shown there is the signed record that this repository's
   workflow built it. The GitHub release page also carries
   `sbom.spdx.json`, a software bill of materials (SBOM): the package and
   every package installing it brings, at the versions `uv.lock` names. A
   scanner reads it to tell whether a newly published vulnerability touches
   a release.

## A uv workspace: more than one package

Skip this section unless the root `pyproject.toml` has a
`[tool.uv.workspace]` table. A uv workspace is one repository that holds
several packages, the root and its members. When the root depends on a
member, installing the root from PyPI needs that member on PyPI too. So one
tag publishes the root and every member that is a package. A member that is
not a package (no `[build-system]`, or `package = false` under `[tool.uv]`)
is not built and not published. Members released on their own tags, apart
from the root, are not supported.

- **A publisher for each package, once, by you.** Repeat step 2 for every
  member that is published: check its name is free, then add one pending
  publisher for each of them, with the member's `name` as the PyPI Project
  Name and the other four fields as in the table. For the practice run, the
  same on TestPyPI.
- **The tag is the root's version.** The tag is checked against the root's
  `pyproject.toml` only. Each member keeps its own version, in its own
  `pyproject.toml`: the root can be at `0.2.0` and a member at `1.0.0`.
- **A member is uploaded only at a new version.** PyPI never takes a
  version twice. A member whose version did not change since the last
  release is on PyPI already, so its files are skipped and the run goes on.
  When a member's code changed, raise its version in the same pull request
  as the root's (`uv version --package <member> 1.0.1`): without that, PyPI
  keeps the member's old files and the new root installs the old member.
- **Not yet checked on a tag run.** Building every package and installing
  the root with its members are tested; the upload of several packages from
  one run is not. Rehearse on TestPyPI first (step 4.2). If the first run
  uploads one package and PyPI refuses another, re-run its failed jobs,
  and again while PyPI refuses a package it has not seen before: the files
  it already has are skipped.

## When a release fails

Nothing is uploaded until every check before the upload has passed. The run
says which step stopped, in its summary.

- **"The tag and the version differ."** The tag says one version,
  `pyproject.toml` another. The wrong tag stays: the repository's tag
  ruleset (when plinth set one up) refuses to move or delete a `v*` tag, so
  its version number is used up. If the file's version has no tag yet, tag
  `origin/main` with it as in step 4. Otherwise raise the version in a pull
  request to one with no tag, merge it, and tag that.
- **"The tag is not on main."** The tag points at a commit that never went
  through a pull request. It stays, as above: tag `origin/main` as in step
  4, with a version that has no tag yet.
- **"PyPI did not accept this release" and `invalid-publisher` in the log.**
  PyPI has no publisher that matches. Check every field of step 2 against
  this repository, for the right site (PyPI or TestPyPI), fix the one that
  differs, then open the failed run and press **Re-run jobs** > **Re-run
  failed jobs** (or `gh run rerun <run id> --failed`). The tag stays as it
  is.
- **"File already exists".** That version was published before, and PyPI
  never takes the same version twice, even after a deletion. Raise the
  version (step 4.1) and tag again. In a uv workspace the run skips such a
  file instead (see "A uv workspace: more than one package").

To take a broken release out of reach without breaking anyone who already
pinned it, *yank* it on PyPI (the project's **Manage** > **Releases** >
**Options** > **Yank**) and publish a fixed version.
