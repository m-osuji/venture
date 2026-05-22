# Testing Summary

This document summarises the automated and repeatable testing carried out for the Venture project, using the merge-ready backend coverage branch results that are intended to land in `main`.

## Testing Strategy

The project uses a mixed testing approach:

- Backend unit and integration-style tests with `pytest`
- Frontend automated tests with `jest`
- Repeatable system testing of the full gameplay flow using documented manual steps

The backend test suite focuses on game logic, API routes, AI helper behaviour, quiz handling, database helpers, and service-layer orchestration. The frontend test suite focuses on page-level behaviour in the browser-facing code. Full end-to-end browser automation is not yet implemented, so system testing is documented as a repeatable manual process.

## Automated Test Commands

### Backend

Run the backend tests with:

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -m "not slow"
```

Current backend result from the merge-ready coverage branch:

```text
122 passed, 2 deselected
```

The two deselected tests are slow Granite/model-related tests that depend on external model availability and are therefore excluded from the normal fast automated pipeline.

### Frontend

Run the frontend tests with:

```powershell
cd frontend\venture-app
npm.cmd test -- --runInBand
```

Current result on `main`:

```text
4 test suites passed
25 tests passed
```

The frontend automated tests currently cover the existing Jest/jsdom page tests in `frontend/venture-app/test`.

## Coverage Summary

`coverage.py` is not installed in the Python virtual environment, so backend coverage was estimated using Python's built-in `trace` module. This is still useful evidence, but it should be described as an estimate rather than a formal `coverage.py` report.

Backend coverage reported by the merge request pipeline:

```text
85.00%
```

This is the authoritative coverage figure reported by GitLab for the merge request pipeline.

For local analysis, Python's built-in `trace` module was also used to estimate backend app-code coverage during development. That local estimate was lower than the pipeline result, so the pipeline figure should be treated as the final headline number for assessment purposes.

Key backend files:

| File | Estimated Coverage |
|---|---:|
| `backend/helpers/gameplay_helpers.py` | 83.2% |
| `backend/helpers/quiz_helpers.py` | 80.1% |
| `backend/ai_opponent/agents/decision_maker.py` | 75.0% |
| `backend/ai_opponent/agents/commentator.py` | 71.9% |
| `backend/routes/api.py` | 84.5% |
| `backend/ai_opponent/knowledge_profile.py` | 77.7% |
| `backend/ai_opponent/agents/negotiator.py` | 79.7% |
| `backend/services/game_service.py` | 83.5% |
| `backend/app.py` | 90.3% |
| `backend/enums.py` | 100.0% |

Interpretation:

- The merge request pipeline reports 85.00% coverage, which is strong evidence of broad automated test coverage across the codebase.
- The gameplay helpers, decision maker, API layer, negotiator, quiz logic, and service layer all have meaningful automated coverage.
- The weaker remaining areas are concentrated in a few AI/helper modules rather than the core round-flow logic.
- Frontend automated test coverage is demonstrated by the passing Jest suites, but there is not currently a quantified whole-frontend line coverage report.

## What The Automated Tests Cover

### Backend

The backend suite includes tests for:

- API endpoints for game state, game status, game start, demo start, demo step, plan notes, orders, quiz results, AI decisions, and commentary
- Flask app creation and route registration
- Commentator helper logic and fallback behaviour
- Database helper behaviour
- Decision-maker heuristics and legal-action generation
- Enum values
- Game service orchestration, alliance lifecycle, demo support, and round resolution
- Gameplay helper functions and round progression
- Knowledge profile behaviour
- Model loader behaviour
- Negotiator behaviour
- Quiz helper functions

### Frontend

The frontend automated suite currently includes tests for:

- Home page behaviour
- Tutorial page behaviour
- Game page behaviour
- Quiz page behaviour

### Manual System Test Cases

`ST-01` Start a new game  
Steps: Open the app and start a new session.  
Expected result: A game state is created and the board loads without backend errors.

`ST-02` Check API health  
Steps: Visit `/api/game/status` and `/api/game/state` during an active session.  
Expected result: Status returns active session data and state returns the frontend-safe game state.

`ST-03` Advance through stages  
Steps: Use the UI controls to progress through the round flow.  
Expected result: The stage label changes correctly and the UI remains usable.

`ST-04` Submit planning notes  
Steps: Enter planning-stage notes for a team and continue.  
Expected result: Notes are accepted and no validation errors occur.

`ST-05` Negotiation flow  
Steps: Enter or trigger negotiation-stage behaviour and proceed.  
Expected result: Declared moves are recorded and stage progression continues.

`ST-06` Orders submission  
Steps: Submit moves/orders for the active round.  
Expected result: Orders are recorded and the game advances to resolution.

`ST-07` Quiz resolution  
Steps: Complete a quiz conflict.  
Expected result: The result is applied and market ownership / round outcome updates correctly.

`ST-08` Commentary endpoint  
Steps: Trigger AI commentary or call `/api/ai/commentary` during an active session.  
Expected result: Commentary JSON is returned with summary and taunt fields.

`ST-09` Demo mode  
Steps: Start the scripted demo and step through it.  
Expected result: Demo state is seeded and the scripted step progression works without crashing.

`ST-10` Error handling  
Steps: Call game endpoints with no active game or invalid IDs.  
Expected result: The API returns structured error responses rather than crashing.

## Evidence That Testing Is Repeatable

The following make the testing process repeatable:

- Exact commands are provided for backend and frontend automated tests
- The main backend suite is automated and fast enough to run routinely
- Frontend automated tests run from the existing `npm` script
- System-test scenarios are listed as explicit repeatable flows rather than informal ad hoc checks

## Known Limitations

- There is no full browser end-to-end automation suite yet
- Frontend line coverage is not currently reported
- Backend coverage is currently estimated with `trace` because `coverage.py` is not installed in the venv
- Slow Granite/model-dependent tests are intentionally excluded from the standard fast automated run because they rely on model availability outside normal local/CI conditions