# BOM CSV Parse Fix Design

## Problem

POST `/import/csv` returns 400 with `"Missing required columns: end_time, exercise_title, set_index, start_time, title"` when the CSV has a UTF-8 BOM (`\ufeff`) prefix. The BOM causes `csv.DictReader` to read the first column as `\ufefftitle` instead of `title`, making all required column comparisons fail.

Additionally, `ParseError` details are not logged — only the resulting `status_code=400` appears in the request log.

## Solution: Approach 1 (Minimal fix)

### 1. BOM stripping in the parser

**File**: `workout_mcp/parser.py`

- In `parse_hevy_csv()`, strip `\ufeff` from the source text before creating `csv.DictReader`
- The parser already receives a `TextIO` object; read its content, strip the BOM, and wrap in a new `StringIO`
- Add `import io` to the parser module

### 2. Log parse errors in the API handler

**File**: `workout_mcp/api.py`

- In the `ParseError` exception handler (line 137–138), add `logger.warning("parse_error", error=str(exc))`
- This ensures the parse error message appears in the log, paired with the request_id from middleware

### 3. Tests

- **Parser test**: CSV string with `\ufeff` prefix (BOM) should parse successfully
- **API test**: POST with BOM-prefixed CSV bytes should return 200

## Files changed

- `workout_mcp/parser.py` — BOM stripping logic, add `import io`
- `workout_mcp/api.py` — log parse error warning
- `tests/test_parser.py` — add BOM test case
- `tests/test_api.py` — add BOM test case
