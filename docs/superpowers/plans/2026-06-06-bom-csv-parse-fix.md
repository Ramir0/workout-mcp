# BOM CSV Parse Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 400 error on `/import/csv` when CSV has UTF-8 BOM prefix, and log parse error details.

**Architecture:** Strip BOM (`\ufeff`) from CSV text in `parse_hevy_csv()` before creating `csv.DictReader`. Add `logger.warning` call in API handler's `ParseError` catch block so error details appear in server logs.

**Tech Stack:** Python 3.13+, csv module, structlog, FastAPI, pytest

---

### Task 1: Write failing parser test for BOM-prefixed CSV

**Files:**
- Modify: `tests/test_parser.py` (add test after line 225)

- [ ] **Step 1: Add BOM test case**

Add at the end of `tests/test_parser.py`:

```python
def test_parse_csv_with_bom() -> None:
    """CSV with UTF-8 BOM prefix should parse successfully."""
    csv_text = (
        '\ufeff"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"Legs","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat",'
        '"","",0,"normal",100,5,,0,\n'
    )
    routines = parse_hevy_csv(io.StringIO(csv_text))
    assert len(routines) == 1
    workout = routines[0].workouts[0]
    assert workout.start == datetime(2024, 1, 1, 10, 0)
    assert workout.end == datetime(2024, 1, 1, 11, 0)
    assert workout.exercises[0].name == "Squat"
    assert workout.exercises[0].sets[0].weight == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_parser.py::test_parse_csv_with_bom -v
```

Expected: FAIL with `MissingColumnError` — confirms BOM causes the bug.

### Task 2: Implement BOM stripping in parser

**Files:**
- Modify: `workout_mcp/parser.py:115-117`

- [ ] **Step 1: Add BOM stripping logic**

In `parse_hevy_csv()`, read the source content and strip leading `\ufeff` before creating `DictReader`:

```python
def parse_hevy_csv(source: TextIO) -> list[ParsedRoutine]:
    """Parse a Hevy CSV export into a nested workout structure."""
    content = source.read()
    if content.startswith("\ufeff"):
        content = content.removeprefix("\ufeff")
    reader = csv.DictReader(io.StringIO(content))
```

Keep the rest of the function exactly as-is.

- [ ] **Step 2: Run the BOM test to verify it passes**

```bash
uv run pytest tests/test_parser.py::test_parse_csv_with_bom -v
```

Expected: PASS

- [ ] **Step 3: Run all parser tests to check no regressions**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: all tests pass

### Task 3: Write API test for BOM-prefixed CSV

**Files:**
- Modify: `tests/test_api.py` (add test after line 237)

- [ ] **Step 1: Add API BOM test case**

Add at the end of `tests/test_api.py`:

```python
def test_import_csv_with_bom(client: TestClient, db_session: Session) -> None:
    """CSV with UTF-8 BOM prefix should import successfully."""
    csv_bytes = (
        '\ufeff"title","start_time","end_time","description","exercise_title",'
        '"superset_id","exercise_notes","set_index","set_type","weight_kg",'
        '"reps","distance_km","duration_seconds","rpe"\n'
        '"Legs","Jan 1, 2024, 10:00 AM","Jan 1, 2024, 11:00 AM","","Squat",'
        '"","",0,"normal",100,5,,0,\n'
    ).encode("utf-8")
    response = client.post(
        "/import/csv",
        content=csv_bytes,
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created"]["routines"] == 1
    assert data["created"]["sets"] == 1
```

- [ ] **Step 2: Run the API BOM test**

```bash
uv run pytest tests/test_api.py::test_import_csv_with_bom -v
```

Expected: PASS (parser fix from Task 2 already handles the BOM)

### Task 4: Add parse error logging in API handler

**Files:**
- Modify: `workout_mcp/api.py:135-138`

- [ ] **Step 1: Add logger.warning for ParseError**

Change the ParseError handler to log the error:

```python
    try:
        routines = parse_hevy_csv(io.StringIO(content))
    except ParseError as exc:
        logger.warning("parse_error", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 2: Run all tests to verify**

```bash
uv run pytest -v
```

Expected: all tests pass

### Task 5: Run full verification suite

- [ ] **Step 1: Run linter, type checker, and tests**

```bash
uv run ruff check . && uv run mypy . && uv run pytest --cov --cov-report=term-missing --cov-fail-under=90
```

Expected: all pass with coverage >= 90%

### Task 6: Commit

- [ ] **Step 1: Stage and commit**

```bash
git add workout_mcp/parser.py workout_mcp/api.py tests/test_parser.py tests/test_api.py
git commit -m "fix: strip UTF-8 BOM from Hevy CSV imports and log parse errors"
```
