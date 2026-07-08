# AGENTS.md

## Project overview

This repository contains InnSight, a Python 3.13 accommodation recommendation service. It parses Chinese natural-language travel queries, resolves points of interest, searches accommodation data from OpenStreetMap-related services, ranks results by travel-time tiers, and exposes the workflow through a FastAPI API and Typer CLI.

Primary goals:

* Keep changes small, focused, and easy to review.
* Prefer correctness, maintainability, and test coverage over speed.
* Preserve existing public behavior unless the task explicitly asks for a behavior change.

Important areas:

* `src/innsight/pipeline.py`, `src/innsight/recommender.py`, `src/innsight/tier.py`, and `src/innsight/rating_service.py`: core recommendation, ranking, and scoring logic.
* `src/innsight/services/`: service-layer orchestration for accommodation search, geocoding, isochrones, query parsing, and tiering.
* `src/innsight/app.py`, `src/innsight/middleware.py`, and `src/innsight/health.py`: FastAPI application, API routes, middleware, and health endpoints.
* `src/innsight/cli.py`: command-line entry point exposed as `innsight`, `innsight-cli`, and `innsight-api`.
* `src/innsight/config.py`, `.env.sample`, and external client modules such as `nominatim_client.py`, `overpass_client.py`, and `ors_client.py`: configuration and third-party service integration.
* `tests/`: pytest test suites, including API, CLI, service, parser, ranking, caching, health, integration, and playground/performance tests.
* `README.md`: user-facing setup, configuration, usage, and service documentation.

## Working loop

For every non-trivial task, follow this loop:

1. Understand the task and identify the smallest relevant area of the codebase.
2. Read the relevant files before editing.
3. Make one focused change at a time.
4. Run the narrowest relevant check first.
5. If the check fails, inspect the failure, form a new hypothesis, and make one focused follow-up change.
6. Repeat until the acceptance checks pass or progress is blocked.
7. Before finishing, summarize:

   * root cause or rationale
   * files changed
   * commands run
   * verification result
   * remaining risks or follow-up work

Do not make broad refactors while fixing a narrow bug.

## Progress log

For tasks requiring more than two iterations, keep a short progress log in:

`.codex/progress.md`

After each iteration, record:

* hypothesis
* files changed
* command run
* result
* next step

## Setup commands

Use these commands unless a nested `AGENTS.md` or `AGENTS.override.md` says otherwise.

```bash
poetry install
```

Examples:

* Install runtime and development dependencies with `poetry install`.
* Use Python 3.13, matching `pyproject.toml`.
* Copy `.env.sample` to `.env` before running commands that need external service configuration.

## Build commands

```bash
poetry build
```

Examples:

* `poetry build`
* `poetry run uvicorn innsight.app:app --reload`
* `poetry run innsight --help`

## Test commands

Run the smallest relevant test first.

```bash
poetry run pytest path/to/test_file.py
```

Examples:

* `poetry run pytest tests/test_app.py`
* `poetry run pytest tests/services/test_accommodation_search_service.py`
* `poetry run pytest tests/test_recommender.py::test_name`

Before finalizing a larger change, run the broader validation command:

```bash
poetry run pytest
```

Examples:

* `poetry run pytest`
* `poetry build`

If a full test suite is slow, ask before running it unless the user explicitly asked for full verification.

## Code style

Follow the existing style of the surrounding code.

General rules:

* Keep functions small and focused.
* Prefer clear names over clever abstractions.
* Do not introduce new dependencies unless necessary.
* Avoid large, unrelated rewrites.
* Preserve public APIs unless the task explicitly asks for a breaking change.
* Update documentation when changing public behavior.

Language-specific rules:

* Python: target Python 3.13 and follow the existing style in `src/innsight`.
* Python: use type hints for new public functions and dataclass/model fields when practical.
* Python: keep FastAPI request/response behavior explicit and covered by tests when API behavior changes.
* Python: avoid adding runtime network calls outside the existing client/service boundaries unless the task requires it and the reason is documented.

## Testing instructions

When changing behavior:

* Add or update tests that cover the changed behavior.
* Prefer integration or end-to-end tests for user-visible behavior.
* Prefer unit tests for isolated logic.
* Include regression tests for bug fixes when practical.

When tests fail:

* Read the first relevant failure carefully.
* Do not blindly change tests to make them pass.
* Only update expected outputs or snapshots when the behavior change is intentional.
* Explain why any snapshot or fixture update is correct.

## Verification loop

After each code change, run:

```bash
./scripts/verify-task.sh
```

If it fails, inspect the first relevant error, make one focused fix, and run it again.
Stop only when `./scripts/verify-task.sh` passes.
Do not broaden the diff or rewrite unrelated code.

For bug fixes:

1. Reproduce or inspect the failure.
2. Identify the smallest likely cause.
3. Make one focused fix.
4. Run the relevant test.
5. If the test fails, use the error output to choose the next hypothesis.
6. Stop when the relevant test passes and no unrelated files were changed.

For feature work:

1. Confirm expected behavior from the issue, docs, or surrounding code.
2. Implement the smallest coherent slice.
3. Add or update tests.
4. Run targeted tests.
5. Run broader checks if the change touches shared code.

For refactors:

1. Preserve behavior.
2. Avoid changing public APIs unless requested.
3. Run tests before and after when practical.
4. Keep the diff reviewable.

## Security and safety

Never:

* Commit secrets, API keys, tokens, credentials, or private certificates.
* Print secrets in logs.
* Modify authentication, authorization, billing, encryption, or data deletion logic without calling it out clearly.
* Run destructive commands such as `rm -rf`, database resets, or production-impacting scripts unless explicitly authorized.
* Add network calls, telemetry, or third-party services without explaining the reason.

If a task touches security-sensitive code, stop and explain:

* what files are affected
* what risk is involved
* what verification was performed
* what still needs human review

## Database and migrations

Before changing database schema:

* Explain why the migration is needed.
* Check existing migration patterns.
* Include rollback or mitigation notes when applicable.
* Do not edit old migrations unless the project convention explicitly allows it.

After changing database-related code:

* Run the relevant migration/test command.
* Mention any manual deployment or migration steps in the final response.

## API and compatibility

When changing APIs:

* Preserve backward compatibility unless the task explicitly asks otherwise.
* Update request/response types, validation, tests, and docs together.
* Note any breaking changes in the final summary.

## UI changes

When changing user-facing UI:

* Keep changes consistent with existing design patterns.
* Update snapshots, visual tests, or story files when the project uses them.
* Mention any accessibility considerations if relevant.

## Documentation

Update documentation when:

* public behavior changes
* setup steps change
* commands change
* configuration changes
* an important architectural decision is introduced

Prefer concise docs close to the changed code.

## Git and pull request expectations

Before finalizing:

* Review the diff for unrelated changes.
* Revert accidental formatting or generated-file changes.
* Ensure tests or checks have been run, or explain why they were not run.

Final response should include:

* Summary of changes
* Tests/checks run
* Any skipped checks and why
* Risks or follow-up work

Do not create commits unless the user asks.

## When blocked

If blocked, do not keep guessing. Report:

* what you tried
* what failed
* the most relevant error message
* the next recommended step
* whether human input, credentials, dependency installation, or environment access is needed

## Source notes

This template is based on:

* OpenAI Codex guidance for `AGENTS.md`, including global/project/nested instruction discovery, override behavior, and using repository-level instructions for consistent expectations.
* The AGENTS.md open format, especially its recommendation to include project overview, build and test commands, code style, testing instructions, and security considerations.
* OpenAI Codex repository examples that emphasize scoped test commands, formatting commands, avoiding unnecessarily large modules, keeping changes reviewable, and giving explicit code review rules.
