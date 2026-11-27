# The plan: how it is written

`plan.md` is the plan (spec chapter 10 until #767), and `plan.ko.md` is its Korean edition; the two say the same and keep the same ids. This page says how an entry in them is written. Entries added from 2026-11-27 on follow it; older text is brought to it when it is next edited.

## What lives where

| A reader asks | It is in |
|---|---|
| What the rule is | the spec, `docs/spec/` |
| Why it was decided so | a decision record, `docs/adr/` |
| What is built when, and what a ticket has to know before it is cut | this folder |
| What changed, and when | git's history |
| What is done and what is next | the issues; #43 maps the tickets to them |

A fact has one home. Another place that needs it points there and does not repeat it.

## A milestone entry

A row of the milestone table (10.0) keeps its five columns: the milestone, its stage, what the user can use right away, the end conditions, the command to show. The row says what is true when the milestone ends.

## A ticket entry

```
**T<m>.<n> `type(scope): summary`** · `M<m>` `<package>` · <size> · Blocked by: <ids or none> · §<spec sections>
- Context: what it builds, in the spec's words.
- Done means: what a person runs and sees.
- Acceptance: the tests, by path and name.
- Notes:
  - <note lines, below>
```

The first line is the one `tests/repo/ticket_graph.py` reads. A ticket that is removed keeps its line with what replaced it, and its number is not used again.

## A note line

A note is something the session that cuts the ticket has to know and the entry's Context does not say. One fact per line, at most two sentences, in the present tense, with no account of how it came about. It opens with its kind and, in brackets, where it came from and when:

- `decided (<source>, <date>): <what holds>.`
- `owner decides at the cut (<source>, <date>): <the choice>.`
- `builder's choice (<source>, <date>; recommended: <which>, because <reason>): <the choice>.`
- `carried (<source>, <date>): <what is still to be done or known here>.`

The source is an issue number with its decision number or section (`#725 Decisions 103`, `#705 Not sure yet`), where the full text stays. Lines from several sources that say the same thing are written once with all their sources. A line a later decision replaces is removed; git keeps it. When the ticket is cut, its notes go into the issue and leave this file in the same pull request.

Lines for work that has no ticket yet are written the same way under "Work with no ticket yet", at the end of 10.1, until their ticket is cut.

## A rule across tickets

A rule every ticket follows, such as how a split ticket names its pull requests, is one line in "Ticket rules" (10.0) with the decision it comes from. A rule of the engine goes to the spec, not here.

## What is not written here

- History: what an entry used to say, which review asked for it, which version added it.
- Status: whether a ticket is done is its issue's to say.
- A count kept by hand. A count that matters is computed by a test.

## The guide on a closed issue

When an issue that collected decisions is closed, its body is not trimmed, since other documents cite its numbered lines. A guide goes above the body:

```
> **Closed <date>. Where its content is now:**
> - Rules: the spec, sections <list>.
> - Reasons: decision records <numbers>.
> - Still to build: `docs/plan/`, under <ticket ids or "Work with no ticket yet">.
> - Not carried: <which parts, and why: done, or replaced by <decision>>.
> The text below is the record as it stood; it is not updated.
```

Then `## Outcome`, as for any task.
