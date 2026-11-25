# 52. Open fills are capped by opening-auction volume when it is given, with a comparison mode

- Status: Accepted
- Date: 2026-11-25
- Amends: [ADR 0006](0006-daily-state-machine-and-the-order-types-are-in-v1.md)
- Spec: §5.6.6, §3.8 (the first screen), §12.1 V31-32

## Context

ADR 0006 approximates capacity by the past 20-session average volume and says it is not an open-auction liquidity measure. The spec's second term, `ψ · volume_t`, caps a fill by the whole session's volume, also for a fill at the open, which can fill more at the open than the auction traded. A user who has the auction's volume has no way to give it, and a user who distrusts the after-the-fact term has no way to see what it changed (#725 Decisions 242, 243).

## Decision

When the bars hold the optional column `open_auction_volume` (added to TDS with #752), an open fill's second term is `ψ_open · open_auction_volume_t`, `ψ_open = [execution] max_open_auction_participation`, default 0.10, a ratio of its own (#752's Decisions, 2026-11-25). The column has `volume`'s unit and adjustment; only the fill reads it, never a term or a decision (235). Without it, `ψ · volume_t` stays as a ceiling only, and the label reports the fills it bound (242).

`[execution] volume_cap = "prior"` is a comparison mode that keeps only the first term, data before the fill session alone; the default `"session"` keeps both, and the label says which ran and how many fills the session term bound (243).

## Considered options

- **Keep the whole-session cap for open fills.** Simple, but it overstates what can fill at the open for a user who has the auction's volume.
- **Use the prior-only cap by default.** No after-the-fact input, but it allows fills larger than a thin session traded; the owner kept it as a comparison.

## Consequences

ADR 0006's approximation stands as the default; a package that gives the auction's volume gets a tighter open cap, and the comparison mode makes the session term's effect visible. `open_auction_volume` joins TDS in V1, and the two settings join spec 3.11's table with the code that reads them.
