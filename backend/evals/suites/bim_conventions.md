# Snowdon Towers question conventions

The rules every gold query follows, in the 85-question set (`bim_snowdon.jsonl`)
and the held-out set (`bim_snowdon_heldout.jsonl`). Written down on 2026-11-12 from
the 85-question gold SQL, before any held-out question was written.

## Which models a question covers

The project is six discipline models, one `BimDocument` each: Architectural
(`SNOWDON_ARCH.r2027`), Structural, Plumbing, HVAC, Site and Electrical.

| The question... | The gold query counts | Example |
|---|---|---|
| names a discipline ("in the electrical model") | that model only | lighting fixtures in the electrical model |
| names no discipline | every model | warnings (92), families (367), ducts |
| is about the levels themselves (how many, elevation, highest) | the architectural model's levels only: every model has its own copy | "How many levels does the building have?" = 18 |
| uses a level as a location ("on level L4") | that level name in every model | plumbing fixtures on L4 |

Phases repeat in every model too; a question about the phases themselves uses
the architectural model's (no 85-set question does this yet).

## What gets counted

- **Placed items** (doors, walls, windows, fixtures, ...) are rows of `FamilyInstance`.
  "How many doors" counts placed doors, not door types or families. Types and
  families are counted only when the question asks about types or families.
- **Design options**: only the main model and the primary option count
  (`Element.DesignOption IS NULL` or `IsPrimary = 1`). In this model only 10 rooms
  sit in non-primary options, so this matters for room questions only.
- **Values** are read from `Parameter` rows named by `ParameterDescriptor.Name`
  when there is no dedicated column (fire rating, occupancy, finishes, ...).

## How answers are graded

- Counts must be exact.
- Quantities in natural units: any correct rounding or Revit display format is
  accepted (34.36 SF, 34 SF).
- A fire rating matches any spelling of the same duration (1 HR, 60 MIN, 1-hour);
  NR is not a rating.
- Every question has an answer in the model: no unanswerable questions (those
  live in the safety suite).
- Headline metric: **correct results** (the query the answer cites returns the
  gold rows; extra columns and duplicate rows allowed).
