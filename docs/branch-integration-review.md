# Team branch integration review

Review baseline: `36be0bc` on `main`. Requirements come from the project proposal, the Home contribution's feature document, the weekly-goal task, `CONTRIBUTING.md`, and the integration/database contracts. All incoming commits are preserved through merges; existing quality changes and applied migrations are retained.

| Contribution | Reviewed tip | Integrated behavior |
| --- | --- | --- |
| `Soham-branch` | `03632a6` | Owned, paginated workout history with stable ordering and validated pagination. |
| `feature/home-page` | `2ff26df` | Multi-food meals, live preview, draft reuse/protection, daily nutrients, day navigation, and optional workout details. |
| `custom-workouts` | `756b517` | Private exercise/workout creation and workout deletion, with fixes described below. |
| `weekly-goal-tracker` | `1642500` | Distinct completed-day goals on Home/Progress and recent-week comparison with the current target. |

The onboarding, earlier page integration, design-quality, and suggested-workout branches were already ancestors of the baseline. Their work is retained without repeating their changes or deleting branch pointers.

## Standards

Independent review found four actionable issues in the incoming custom-workout implementation:

- **Ownership (P1):** unfiltered workout/prescription reads and unchecked nested exercise IDs violated the authenticated-owner rule. Lists, detail, logging, deletion and nested creation now consistently allow shared or owned definitions only.
- **JSON writes (P2):** creation returned SQLite Row objects after committing, causing JSON serialization errors. Creation now returns ordinary dictionaries, including complete workout prescriptions, with regression checks for HTTP 201 and persistence.
- **Migration compatibility (P2):** migration 006 added per-owner indexing while inherited global constraints still blocked names across accounts. Additive migration 007 preserves IDs/references/snapshots and fixes name scoping. The runner explicitly supports atomic parent rebuilds, integrity checks and failure rollback; 006 remains unchanged.
- **Validation and transactions (P2):** unchecked nested values caused errors or invalid prescriptions, and transaction ownership was unclear. `custom_catalog.py` validates typed/bounded values and owns each complete transaction. Invalid shapes return structured 422 errors without partial parent records.

A subsequent **P3** review found repeated exercise prescriptions could generate duplicate logging input IDs. Private workout creation now requires distinct exercise IDs; callers adjust the suggested set count instead. The regression cases also cover the maximum total set count using distinct exercises.

Commented-out implementations were removed, the incoming meal tests were moved into CI's test directory, and formatting/syntax checks include the optional browser script. A preview server uses an isolated instance, cookie name, and temporary database.

## Spec

The independent behavior review reproduced four incoming custom-workout problems: cross-account read/log access, successful saves returning 500, per-owner names still blocked globally, and malformed prescriptions returning 500. All four are corrected and covered by regression cases. They overlap the Standards findings because privacy, successful creation, owner-scoped identity, and structured validation are also behavior contracts.

The combined Home retains both the contributor's meal flows and the weekly tracker. History reads stored private logs independently of mutable definitions. Private creation/deletion remains an API capability, matching the incoming backend scope; existing cards/guides/logging display those definitions. A new builder, favorite-food library, in-place activity editing, photos, and generated achievements are separate work.

## Modifiability and patterns

- **Layered modules:** HTTP handlers delegate to catalog readers, private catalog writes, activity writes, or progress readers. Ownership and calculation rules stay out of templates and page controllers.
- **Dependency injection and transaction scripts:** modules accept the database connection and acting account; each private creation/deletion owns a documented atomic transaction. Tests exercise actual SQLite constraints.
- **Shared read models and composition:** Home and Progress share activity reports and the weekly-goal renderer. Meal drafts have a separate pure calculation module used by preview and tests.
- **Forward-only migrations and historical snapshots:** private catalog changes retain record IDs and logged names, muscle metadata and sets. Adding a future field does not require rewriting history.
- **Existing decorators and factory:** authentication/onboarding/CSRF and test application assembly remain centralized.

No repository hierarchy, provider framework, or speculative plugin interface is introduced. Change guidance and endpoint contracts are in [integration.md](integration.md); migration rules are in [database.md](database.md).

## Verification

- All **77 Python tests** and **7 Node tests** pass, including incoming history/meal cases and private catalog regressions.
- Ruff lint/format, template formatting, Prettier, JavaScript syntax and diff checks pass. Meal calculation tests now run in the existing Node test command.
- Headless Chrome checks cover an empty account, multi-food previews and persistence, meal reuse across dates, draft protection, row removal/focus, manual notes/estimates, private definition creation and logging with actual sets, history pagination, and weekly progress on both pages.
- Network failure checks preserve meal drafts/controls and isolate weekly errors from daily data. Keyboard week navigation works. Desktop (1440 px) and phone (375 px) layouts have no horizontal overflow; inspected flows have no browser JavaScript errors.
- Fresh and populated migration upgrades retain IDs, scheduled links, logged names, muscle snapshots and exercise sets. A deliberately failing rebuild rolls back both DDL/data and its version record, restoring foreign-key enforcement. Migrations 001–006 remain unchanged.

Standards: five findings resolved; worst original issue was private catalog access (P1). Spec: four findings resolved; worst original issue was cross-account discovery/logging (P1).
