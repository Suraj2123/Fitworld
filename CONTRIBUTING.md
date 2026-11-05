# Working together on Fitworld

## Branches and review

Start with a clean worktree and fetch the latest `main`. Use a concise task branch such as `fix-weight-checkin` or `add-exercise-guides`; omit `codex` unless explicitly requested. Keep another contributor's work in Git history when integrating their branch.

Keep a pull request focused on one feature or correction. Explain the user-visible problem, the resulting behavior, and the checks run. Mention migrations, changed JSON contracts, and intentionally deferred work. For a formatting change across many files, keep formatting separate from behavior changes when preparing commits; reviewers can use a word diff for mixed changes.

There are no mandatory individual file owners. Coordinate changes to shared files such as `validation.py`, the base template, catalog definitions, and migrations before starting overlapping work. Favor small page/domain modules so unrelated features can change in separate files.

## Development setup

The app runs with Python 3.10+ and `requirements.txt`. The complete development checks use Python **3.11+** (the template formatter requires it) and Node **22+**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
```

Node packages and formatters are development tools only. The app still needs no JavaScript build step. Runtime dependencies are pinned in `requirements.txt`; development tools are pinned in `requirements-dev.txt` and `package-lock.json`.

## Checks before a pull request

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
djlint fitworld/templates --check
npm run format:check
npm run check:js
npm run test:js
git diff --check
```

The GitHub Actions workflow runs the same checks, with application tests on Python 3.10 and 3.14. Formatting checks validate the code; they do not replace behavior tests or browser review. For changed interactions, verify a fresh and populated account, keyboard use, and a phone-sized viewport.

To apply the agreed formatting:

```bash
ruff check . --fix
ruff format .
djlint fitworld/templates --reformat --quiet
npm run format
```

Review the diff before committing. The template formatter returns a nonzero exit when it changes files; run its `--check` command afterward. SQL migrations should remain readable, with comments describing the data-preservation rule.

## Stable interfaces

- The account in the session is the acting user. Check ownership of parent records before reading/writing private children.
- Controllers call domain/read modules; rendering code does not issue SQL. Keep account/session-specific behavior together in the account feature.
- Preserve JSON field names. Add optional fields for compatible changes; coordinate a new endpoint/version for incompatible ones.
- Store mass in kilograms and actual duration in seconds. Accept explicit local calendar dates. Use the shared validators and measurement writer instead of copying conversion or date logic.
- A profile metadata edit must not be treated as a new measurement. Transaction helpers document whether they own or join their caller's transaction.
- Do not put passwords, session keys, personal databases, node modules, or virtual environments in Git.

## Database changes

Append a uniquely numbered migration and never edit an applied one. Two developers adding the same next number should coordinate and rename the unshared file before merging. Run `init-db` against both a fresh temporary database and a populated previous-version fixture; preserve record IDs and history. Keep SQL foreign keys enabled on every connection.

Exercise identity uses SQLite `NOCASE` consistently. Do not create a second ID just to change capitalization. Seed updates must preserve existing edits; new catalog definitions and workout prescriptions are separate contributions.

## Test scope

Prefer tests through the JSON interfaces used by callers. Use worked examples: two servings at 150 kcal must total 300, and a partial workout must not count as completed. Use the temporary `AppCase` fixture for app tests. Test migrations at the SQL/schema interface, including ownership references and old snapshots; avoid mocking SQLite when its actual constraints matter.

Transport tests run through Node's built-in test runner, with fake HTTP responses at the fetch interface. They do not import a browser DOM or inspect page internals. No new test framework is needed for a small behavior.

See [the design-pattern review](docs/design-and-quality.md) for concrete examples, and [the integration guide](docs/integration.md) for endpoint contracts.
