# Domain docs

Domain documents the engineering skills read **before** exploring the codebase.
(mattpocock/skills seed, MIT.)

## Before exploring, read these

- Root **`GLOSSARY.md`**: the glossary. No implementation detail.
- **`docs/adr/`**: the ADRs for the area you touch.

If either is missing, move on quietly. Do not report it and do not create it
ahead of time; `/domain-modeling` creates them when a term or decision is
actually settled.

## File structure

single-context (this repository):

```text
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-….md
│   └── 0002-….md
└── src/
```

Write an ADR only when all three hold: **hard to reverse**, **surprising without
context**, **the result of a real trade-off**.

An accepted ADR's text is never deleted or rewritten (Nygard's form, as adr-tools
writes it). Replaced whole: its line becomes `- Status: Superseded by [ADR NNNN](file) (date)`
and the new record says `- Supersedes: [ADR MMMM](file)`. Changed in part: it gains one
line `- Amended by: [ADR NNNN](file) (date)` and the change is written in the new record.
