# 53. The hold band is v1 with no default width, and turnover and cost share are always labelled

- Status: Accepted
- Date: 2026-11-25
- Amends: [ADR 0020](0020-a-risk-stage-slot-and-the-target-state-recursion-hold.md)
- Spec: §1.2, §3.7, §5.5.3, §3.8 (the first screen), §10 T7.1, §12 OI-12

## Context

ADR 0020 says the hold band is "implemented as the last v1 ticket (T7.1)". A strategy that trades often needs the band, and its user needs to see what the trading costs, long before the last ticket of the last milestone (#725 Decision 244).

## Decision

The hold band is in v1, off by default, with no default width: it is on only with the `m` the user gives. The rule sentences of the spec say only that. When it is built is the plan's: the owner places it in the first execution slice, and T7.1's place in the ticket graph is set again when stage (2) cuts its tickets; until then the ticket graph keeps T7.1 where it is (#725 Decision 244; #752's Decisions, 2026-11-25).

A run's label always reports turnover and the share of gross P&L that costs take (244).

The band keeps reading the previous decision's canonical target state, as ADR 0020 decided (#752's Decisions, 2026-11-24).

## Considered options

- **Keep the band as the last ticket.** No change to the plan, but a frequently trading strategy would run without it through every earlier milestone.
- **A default width.** Saves a parameter, but any width is a strategy choice the user did not make.

## Consequences

ADR 0020's definition stands; only its place in the plan and the default change. The plan's documents (spec 10's T7.1 entry, 12's OI-12, `START-HERE.md`) carry the timing, the rule sentences none.
