# Replace Webhook Signature with Static API Key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the HMAC-SHA256 signature verification mechanism with a simple static API key check, keeping the `HEVY_WEBHOOK_SECRET` config variable name.

**Architecture:** Rename `SignatureVerificationMiddleware` to `ApiKeyMiddleware`, replace HMAC body verification with a constant-time string comparison of the `X-API-Key` header against `settings.hevy_webhook_secret`, remove the `_verify_webhook_signature` helper, and update all tests and documentation.

**Tech Stack:** Python 3.13, FastAPI, pytest, hmac (for `compare_digest` only)

---

## File Structure

| File | Responsibility |
|------|-------------|
| `workout_mcp/api.py` | FastAPI app, middleware, routes. Modified: rename middleware, swap logic, remove helper. |
| `tests/test_webhook.py` | Webhook endpoint tests. Modified: update auth headers, add missing-header test, add valid-key test. |
| `tests/conftest.py` | Pytest fixtures. Modified: update `_reset_webhook_secret` docstring only. |
| `README.md` | API authentication docs, cURL examples, webhook section. |
| `.env.example` | Environment variable template comments. |
| `.env.docker` | Docker environment variable template comments. |

---

## Task 1: Rename & Swap Middleware Logic (`workout_mcp/api.py`)

**Files:**
- Modify: `workout_mcp/api.py:5-6` (remove `hashlib` import, keep `hmac`)
- Modify: `workout_mcp/api.py:98-115` (rename middleware class, swap logic)
- Modify: `workout_mcp/api.py:259-263` (remove `_verify_webhook_signature`)

- [ ] **Step 1: Remove unused `hashlib` import**

Since we no longer compute HMAC-SHA256 digests, `hashlib` is no longer needed. `hmac` is still needed for `hmac.compare_digest`.

```python
# Before:
import hashlib
import hmac

# After:
import hmac
```

- [ ] **Step 2: Rename middleware class and swap its logic**

Replace the `SignatureVerificationMiddleware` class (lines 98-112) with `ApiKeyMiddleware`:

```python
class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Verify X-API-Key header on all requests when HEVY_WEBHOOK_SECRET is configured."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if settings.hevy_webhook_secret:
            api_key = request.headers.get("X-API-Key")
            if api_key is None or not hmac.compare_digest(api_key, settings.hevy_webhook_secret):
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid API key"},
                )
        return await call_next(request)
```

Also update the `add_middleware` call on line 115:

```python
# Before:
app.add_middleware(SignatureVerificationMiddleware)

# After:
app.add_middleware(ApiKeyMiddleware)
```

- [ ] **Step 3: Remove `_verify_webhook_signature` helper**

Delete lines 259-263 entirely:

```python
def _verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if signature is None:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

- [ ] **Step 4: Commit**

```bash
git add workout_mcp/api.py
git commit -m "feat: replace HMAC signature middleware with static API key middleware"
```

---

## Task 2: Update Webhook Tests (`tests/test_webhook.py`)

**Files:**
- Modify: `tests/test_webhook.py:8-35`

- [ ] **Step 1: Add test for valid API key success path**

Add a new test that verifies the webhook returns 200 when a valid `X-API-Key` is provided and `HEVY_WEBHOOK_SECRET` is configured:

```python
def test_webhook_with_valid_api_key_returns_200(client: TestClient) -> None:
    with (
        patch("workout_mcp.api.settings.hevy_api_key", "test-key"),
        patch("workout_mcp.api.settings.hevy_webhook_secret", "test-secret"),
        patch("workout_mcp.api.HevyClient.get_workout", return_value={}),
        patch("workout_mcp.api.upsert_hevy_workout") as mock_upsert,
    ):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
            headers={"X-API-Key": "test-secret"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_upsert.assert_called_once()
```

- [ ] **Step 2: Update invalid signature test to invalid API key**

Change `test_webhook_invalid_signature_returns_400` to send `X-API-Key: invalid` instead of `X-Hevy-Signature: invalid`, and update the assertion message:

```python
def test_webhook_invalid_api_key_returns_400(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.hevy_webhook_secret", "secret"):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
            headers={"X-API-Key": "invalid"},
        )
    assert response.status_code == 400
    assert "Invalid API key" in response.json()["detail"]
```

- [ ] **Step 3: Add test for missing API key header**

Add a new test that verifies 400 when `HEVY_WEBHOOK_SECRET` is configured but the `X-API-Key` header is missing:

```python
def test_webhook_missing_api_key_header_returns_400(client: TestClient) -> None:
    with patch("workout_mcp.api.settings.hevy_webhook_secret", "secret"):
        response = client.post(
            "/webhooks/hevy",
            json={"workoutId": "test-id-123"},
        )
    assert response.status_code == 400
    assert "Invalid API key" in response.json()["detail"]
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_webhook.py
git commit -m "test: update webhook tests for static API key auth"
```

---

## Task 3: Update Test Fixture Comment (`tests/conftest.py`)

**Files:**
- Modify: `tests/conftest.py:16-19`

- [ ] **Step 1: Update docstring in `_reset_webhook_secret` fixture**

```python
# Before:
@pytest.fixture(autouse=True)
def _reset_webhook_secret() -> Generator[None]:
    """Ensure HEVY_WEBHOOK_SECRET is unset during tests so the signature middleware is bypassed."""
    with patch.object(settings, "hevy_webhook_secret", None):
        yield

# After:
@pytest.fixture(autouse=True)
def _reset_webhook_secret() -> Generator[None]:
    """Ensure HEVY_WEBHOOK_SECRET is unset during tests so the API key middleware is bypassed."""
    with patch.object(settings, "hevy_webhook_secret", None):
        yield
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "docs: update test fixture comment for API key middleware"
```

---

## Task 4: Update README Authentication Docs

**Files:**
- Modify: `README.md:187-289`

- [ ] **Step 1: Rewrite API Authentication section**

Replace the entire "API Authentication (Signature Verification)" section (lines 187-237) with:

```markdown
### API Authentication (API Key)

When `HEVY_WEBHOOK_SECRET` is configured, **all REST API endpoints require an API key**. Every request must include the `X-API-Key` header with the exact value of `HEVY_WEBHOOK_SECRET`.

If the header is missing or the key is invalid, the server responds with `400 Bad Request`.

**To disable API key verification**, leave `HEVY_WEBHOOK_SECRET` unset (default).

#### Example with cURL (JSON endpoint)

```bash
curl -X POST http://localhost:9090/webhooks/hevy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-hevy-webhook-secret" \
  -d '{"workoutId":"abc123"}'
```

#### Example with cURL (multipart file upload)

```bash
curl -X POST http://localhost:9090/import/csv \
  -H "X-API-Key: your-hevy-webhook-secret" \
  -F "file=@hevy_export.csv"
```
```

- [ ] **Step 2: Update import CSV section reference**

On line 250, change:

```markdown
# Before:
When `HEVY_WEBHOOK_SECRET` is configured, include the `X-Hevy-Signature` header as described in [API Authentication](#api-authentication-signature-verification).

# After:
When `HEVY_WEBHOOK_SECRET` is configured, include the `X-API-Key` header as described in [API Authentication](#api-authentication-api-key).
```

- [ ] **Step 3: Update webhook integration env var description**

On lines 267-268, change:

```markdown
# Before:
- `HEVY_WEBHOOK_SECRET`: A shared secret string that you and Hevy agree on to verify webhook authenticity. **Keep this secret secure** — anyone with this secret can forge webhook requests. When set, it applies to **all** REST API endpoints (not just webhooks).

# After:
- `HEVY_WEBHOOK_SECRET`: A static API key. **Keep this secret secure** — anyone with this key can make API requests. When set, all REST API endpoints require the `X-API-Key` header with this exact value.
```

- [ ] **Step 4: Update webhook headers table**

On line 289, change:

```markdown
# Before:
| `X-Hevy-Signature` | `<hex>` | HMAC-SHA256 hex digest of the raw request body, using `HEVY_WEBHOOK_SECRET` as the key. **Required when `HEVY_WEBHOOK_SECRET` is configured.** |

# After:
| `X-API-Key` | `<string>` | Static API key matching the `HEVY_WEBHOOK_SECRET` value. **Required when `HEVY_WEBHOOK_SECRET` is configured.** |
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README for static API key authentication"
```

---

## Task 5: Update Environment Variable Comments

**Files:**
- Modify: `.env.example:13-15`
- Modify: `.env.docker:10-13`

- [ ] **Step 1: Update `.env.example` comments**

```bash
# Before:
# Hevy API (optional — required for webhook sync and automatic workout fetching)
HEVY_API_KEY=your-hevy-api-key
HEVY_WEBHOOK_SECRET=your-hevy-webhook-secret

# After:
# Hevy API (optional — required for webhook sync and automatic workout fetching)
HEVY_API_KEY=your-hevy-api-key
# When set, all REST API endpoints require the X-API-Key header with this exact value
HEVY_WEBHOOK_SECRET=your-hevy-webhook-secret
```

- [ ] **Step 2: Update `.env.docker` comments**

```bash
# Before:
# Hevy settings
HEVY_API_KEY=your-hevy-api-key
HEVY_BASE_URL=https://api.hevyapp.com
HEVY_WEBHOOK_SECRET=your-hevy-webhook-secret
HEVY_SYNC_INTERVAL_SECONDS=3600

# After:
# Hevy settings
HEVY_API_KEY=your-hevy-api-key
HEVY_BASE_URL=https://api.hevyapp.com
# When set, all REST API endpoints require the X-API-Key header with this exact value
HEVY_WEBHOOK_SECRET=your-hevy-webhook-secret
HEVY_SYNC_INTERVAL_SECONDS=3600
```

- [ ] **Step 3: Commit**

```bash
git add .env.example .env.docker
git commit -m "docs: update env comments for static API key semantics"
```

---

## Task 6: Run Full Test Suite

**Files:** N/A (verification step)

- [ ] **Step 1: Run tests**

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest
```

Expected: All tests pass.

- [ ] **Step 2: Run tests with coverage**

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/workout_mcp_test uv run pytest --cov --cov-report=term-missing --cov-fail-under=90
```

Expected: All tests pass, coverage ≥ 90%.

- [ ] **Step 3: Run linter and formatter**

```bash
uv run ruff check .
uv run ruff format .
```

Expected: No errors, no formatting changes.

- [ ] **Step 4: Run type checker**

```bash
uv run mypy .
```

Expected: No type errors.

- [ ] **Step 5: Commit (if any formatting changes)**

```bash
git diff --quiet || (git add -A && git commit -m "style: format after implementation")
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| Rename `SignatureVerificationMiddleware` → `ApiKeyMiddleware` | Task 1, Step 2 |
| Replace HMAC-SHA256 with static key comparison | Task 1, Step 2 |
| Remove `_verify_webhook_signature` helper | Task 1, Step 3 |
| Update error message to "Invalid API key" | Task 1, Step 2 |
| Remove body-reading/caching from middleware | Task 1, Step 2 (new middleware does not touch body) |
| Update `test_webhook_invalid_signature_returns_400` | Task 2, Step 2 |
| Add `test_webhook_missing_api_key_header_returns_400` | Task 2, Step 3 |
| Add `test_webhook_with_valid_api_key_returns_200` | Task 2, Step 1 |
| Update `tests/conftest.py` comments | Task 3 |
| Update README auth docs and examples | Task 4 |
| Update `.env.example` and `.env.docker` comments | Task 5 |
| Full test suite passes with ≥90% coverage | Task 6 |

---

## Placeholder Scan

- No "TBD", "TODO", "implement later", or "fill in details" found.
- No vague "add error handling" or "handle edge cases" steps — all steps include exact code.
- All test steps include actual test code.
- No "similar to Task N" references.

---

## Type Consistency Check

- `hmac.compare_digest` is used with two strings (header value vs. settings value) — correct signature: `compare_digest(str, str) -> bool`.
- `ApiKeyMiddleware.dispatch` returns `Response` — consistent with `BaseHTTPMiddleware` interface.
- `JSONResponse(status_code=400, content={"detail": "Invalid API key"})` — consistent with existing error response format.
