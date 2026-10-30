---
name: verify
description: Before a commit, clean up the change within its agreed behaviour, then run this repository's checks, the commands in AGENTS.md's code block, then the test that runs the program and report what it printed.
---

# Verify

## 1. Clean up the change

A pass over the change about to be committed, after it works and before the
commit. It keeps the agreed behaviour, the tests and `AGENTS.md`'s rules
exactly as they are; it changes only how the change is written.

- Reuse a helper that already exists instead of a new one beside it.
- Remove an abstraction with one use, and scaffolding for a need nobody has yet.
- Before adding a dependency, check what the standard library, the platform or
  a dependency already installed does.
- Prefer the shorter form of the same logic.
- Remove wasted work the change adds: the same computation or I/O repeated,
  independent steps run one after another, blocking work at startup or on a
  hot path.

Never cut validation at a trust boundary, error handling that prevents a loss,
a security measure, or anything the issue asked for. When unsure, keep it.

On a commit that answers a review finding, the pass covers only the lines that
fix touches: the diff the reviewer read is not reshuffled under them.

## 2. Run the checks

Run the commands in the code block at the top of `AGENTS.md`, in that order.
That block is the only list: do not keep a second copy of the commands here or
anywhere else.

- A command that fails stops the commit. Report it with its output.
- A check that looks wrong, such as a test of the old behaviour after an
  intended change, is said to be wrong and fixed in the same change, or the
  person is asked. Never commit over a failing check in silence.
- CI runs the same checks as required checks and is the gate. This is the
  early look, so a failure costs a commit instead of a pull request round.

## 3. Run the program

Run `tests/test_built_wheel.py` alone: the pytest command in `AGENTS.md`'s
code block, with the file and `-v` after it. It builds the wheel and calls the
package's public name from it, as a person who installs the package does, not
from the source tree.
Step 2's `pytest` ran it among the others; run alone, its result is its own.

Put what you ran and saw in the report, not a summary of it:

- the command, exactly as run;
- its exit status;
- the first lines of its output, up to 20, as printed;
- the commit it ran on (`git rev-parse --short HEAD`), and whether the working
  tree had changes not yet committed (`git status --short`).

A failure here stops the commit like any other. A change to the public name or how
the package is built changes this test with it, in the same change.

This skill runs the checks and this one test of the program, not the app any
further. It takes the place of Claude Code's bundled `/verify`, which builds
and runs the app; to see the change working in the running app, use the
bundled `/run`.

What you tell the person while you do this, from the first line after this
skill loads to the report, is in the language they write in, not in this
file's.
