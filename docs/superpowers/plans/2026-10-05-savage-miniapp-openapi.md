# SAVAGE Mini Program OpenAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a tested OpenAPI 3.1 description and installable Codex skill that can obtain a SAVAGE bearer token and create one unpaid class order with explicit user approval.

**Architecture:** `openapi.yaml` is the contract. A Python standard-library client implements a small, deterministic subset of that contract, while `SKILL.md` controls token capture and the safe booking sequence. Unit tests use a local HTTP server; CI validates the contract, safety invariants, skill metadata, and client behavior without contacting SAVAGE.

**Tech Stack:** OpenAPI 3.1 YAML, Python 3.11 standard library, pytest, PyYAML, Redocly CLI, GitHub Actions, static Swagger UI.

**Spec:** `docs/superpowers/specs/2026-10-05-savage-miniapp-openapi-design.md`

## Global Constraints

- The project is unofficial and only supports accounts that the user owns or controls.
- Never commit or print a real token, login code, user ID, union ID, order ID, proxy capture, or personal response.
- Do not define or call `payment/prepay` or `wx.requestPayment`.
- Treat the login response `expireTime` as authoritative; do not claim refresh-token support.
- Require explicit approval immediately before each `order/place` request.
- Send at most one `order/place` request per approval and check `TO_PAY` after any uncertain response.
- Stop on API codes `401`, `411`, `412`, `429`, `400`, or `500`; do not use concurrent requests or high-frequency polling.
- Automated tests must use a local mock server and must never call the production API.
- Documentation uses clear, direct Simplified Technical English.

## Review Focus

- A response can have HTTP 200 and a non-200 envelope code; the client must fail closed.
- A timeout after `order/place` is ambiguous; the client must query `TO_PAY`, not place again.
- A matching unpaid order can already exist; the client must stop before settlement and placement.
- Settlement identifiers can be absent or malformed; the client must stop before placement.
- Secrets can leak through CLI output, exceptions, examples, or tracked files; tests and CI must detect these routes.

---

### Task 1: OpenAPI Contract and Safety Tests

**Files:**
- Create: `openapi.yaml`
- Create: `tests/test_openapi.py`
- Create: `requirements-dev.txt`

**Interfaces:**
- Consumes: Verified endpoint and payload details from the design spec.
- Produces: OpenAPI operations and schemas consumed by documentation and client tests.

- [ ] **Step 1: Write failing contract tests**

Add tests named `test_required_operations_are_documented`, `test_protected_operations_use_bearer_auth`, `test_payment_operations_are_absent`, `test_place_declares_real_order_side_effect`, `test_examples_contain_no_secret_shapes`, and `test_business_error_envelopes_are_documented`. Assert the exact paths, operation IDs, security declarations, side-effect marker, and API codes from the spec.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/test_openapi.py -v`

Expected: FAIL because `openapi.yaml` does not exist.

- [ ] **Step 3: Implement the OpenAPI 3.1 contract**

Define the production server, `bearerAuth`, public and protected operations, request/response examples, the `{code,msg,data}` envelope, reusable schemas, and documented business errors. Use placeholder IDs and tokens only.

- [ ] **Step 4: Validate and verify GREEN**

Run: `python3 -m pytest tests/test_openapi.py -v && npx --yes @redocly/cli lint openapi.yaml`

Expected: all tests pass and Redocly reports no errors.

- [ ] **Step 5: Commit**

Run: `git add openapi.yaml tests/test_openapi.py requirements-dev.txt && git commit -m "feat: document SAVAGE OpenAPI contract"`

### Task 2: Safe API Client

**Files:**
- Create: `scripts/savage_api.py`
- Create: `tests/test_savage_api.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: The endpoint paths and field names in `openapi.yaml`.
- Produces: `SavageClient`, `ApiError`, `list_classes(query)`, `inventory(schedule_id)`, `list_orders(scene)`, `settle(schedule_id)`, `place(settlement, approved)`, and `book_unpaid(schedule_id, approved)`.

- [ ] **Step 1: Write failing client and mock-server tests**

Cover a normal list/inventory/settle/place flow, HTTP-200 business errors, `401`, `429`, existing matching `TO_PAY`, malformed settlement data, secret redaction, refusal without approval, and the timeout-after-place reconciliation flow.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/test_savage_api.py -v`

Expected: FAIL because `scripts.savage_api` does not exist.

- [ ] **Step 3: Implement the minimal client library**

Use `urllib.request` with bounded timeouts. Parse both HTTP errors and envelope codes. Redact authorization data from every raised message. Model uncertain placement as a distinct error that requires `list_orders("TO_PAY")` before any later placement.

- [ ] **Step 4: Add the guarded CLI**

Add subcommands `classes`, `inventory`, `orders`, `settle`, and `book-unpaid`. Read the bearer token from `SAVAGE_TOKEN_FILE`, require its file mode to exclude group/other access, display a booking summary, and require an exact interactive confirmation before calling `order/place`.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python3 -m pytest tests/test_savage_api.py -v`

Expected: all tests pass; the mock server records no payment endpoint and no duplicate placement.

- [ ] **Step 6: Commit**

Run: `git add scripts/savage_api.py tests/test_savage_api.py tests/conftest.py && git commit -m "feat: add guarded unpaid booking client"`

### Task 3: Installable Codex Skill

**Files:**
- Create: `SKILL.md`
- Create: `agents/openai.yaml`
- Create: `tests/test_skill.py`
- Create: `tests/skill_scenarios.md`

**Interfaces:**
- Consumes: `scripts/savage_api.py` commands and the safety constraints.
- Produces: An installable `savage-miniapp-openapi` skill with token and unpaid-booking workflows.

- [ ] **Step 1: Record RED baseline scenarios without the skill**

Run the five prompts from the design spec without loading `SKILL.md`. Record the unsafe or incomplete baseline behavior in `tests/skill_scenarios.md`, with no real credentials or live requests.

- [ ] **Step 2: Write failing structural and workflow tests**

Test the required frontmatter, trigger terms, Proxyman scope, token file mode `600`, `401` relogin behavior, duplicate check, approval gate, one-place limit, timeout reconciliation, rate-limit stop, and payment prohibition.

- [ ] **Step 3: Run tests and verify RED**

Run: `python3 -m pytest tests/test_skill.py -v`

Expected: FAIL because the skill files do not exist.

- [ ] **Step 4: Scaffold and implement the skill**

Use the skill-creator initializer for canonical structure, then adapt its generated files to the existing repository root. Keep only `name` and `description` in `SKILL.md` frontmatter. Generate `agents/openai.yaml` from the completed skill and include `$savage-miniapp-openapi` in the default prompt.

- [ ] **Step 5: Run GREEN skill tests and validator**

Run: `python3 -m pytest tests/test_skill.py -v && python3 /Users/ruizhehuang/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`

Expected: all tests pass and the skill validator reports success.

- [ ] **Step 6: Run pressure-scenario review and refine**

Evaluate the five skill prompts with the completed skill. Confirm that every response preserves secrets, checks duplicates, asks for approval, makes no payment, and reconciles uncertain placement before retry. Update wording only when a scenario exposes ambiguity, then rerun Step 5.

- [ ] **Step 7: Commit**

Run: `git add SKILL.md agents/openai.yaml tests/test_skill.py tests/skill_scenarios.md && git commit -m "feat: add safe SAVAGE booking skill"`

### Task 4: Public Documentation and Examples

**Files:**
- Create: `README.md`
- Create: `SECURITY.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `examples/list-classes.json`
- Create: `examples/place-unpaid-order.json`
- Create: `tests/test_repository_safety.py`

**Interfaces:**
- Consumes: OpenAPI operation IDs, CLI commands, and skill workflows.
- Produces: Public setup, token capture, usage, cleanup, legal, and safety guidance.

- [ ] **Step 1: Write failing repository-safety tests**

Test ignored secret/capture filenames, tracked-file secret scanning, placeholder-only examples, required unofficial-use warning, Proxyman cleanup steps, token TTL explanation, and explicit no-refresh-token/no-payment statements.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/test_repository_safety.py -v`

Expected: FAIL because documentation and examples do not exist.

- [ ] **Step 3: Write concise public documentation and sanitized examples**

Document certificate trust, SSL Proxying limited to `wechat-api.savagepark.com.cn`, token capture and `chmod 600`, token expiration from `expireTime`, API/CLI usage, approval behavior, certificate removal, and proxy disablement. State that endpoints are observed and can change.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python3 -m pytest tests/test_repository_safety.py -v`

Expected: all tests pass and the tracked tree contains no credential-shaped value.

- [ ] **Step 5: Commit**

Run: `git add README.md SECURITY.md LICENSE .gitignore examples tests/test_repository_safety.py && git commit -m "docs: add safe public usage guide"`

### Task 5: CI and Static API Reference

**Files:**
- Create: `.github/workflows/validate.yml`
- Create: `.github/workflows/pages.yml`
- Create: `docs/index.html`
- Create: `tests/test_ci.py`

**Interfaces:**
- Consumes: `openapi.yaml`, pytest suite, and skill validator.
- Produces: Pull-request validation and GitHub Pages Swagger UI deployment.

- [ ] **Step 1: Write failing CI configuration tests**

Assert pinned Python and Node setup, pytest, Redocly lint, skill validation, secret scan, no live SAVAGE request, least-privilege workflow permissions, and a Pages document that loads root `openapi.yaml` without embedding credentials.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/test_ci.py -v`

Expected: FAIL because workflow and Pages files do not exist.

- [ ] **Step 3: Implement validation and Pages workflows**

Make validation run on pushes and pull requests. Make Pages deploy only after validation on `main`. Give validation read-only contents access and Pages only the deployment permissions it needs.

- [ ] **Step 4: Run the complete local verification suite**

Run: `python3 -m pytest -v && npx --yes @redocly/cli lint openapi.yaml && python3 /Users/ruizhehuang/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`

Expected: all tests pass, Redocly reports no errors, and skill validation succeeds.

- [ ] **Step 5: Commit**

Run: `git add .github docs/index.html tests/test_ci.py && git commit -m "ci: validate and publish API reference"`

### Task 6: Independent Review and Public Release

**Files:**
- Modify: Any file that fails review.

**Interfaces:**
- Consumes: The complete local repository.
- Produces: Public GitHub repository `savage-miniapp-openapi` on `main`.

- [ ] **Step 1: Audit before publication**

Run the complete verification suite, `git diff --check`, `git status --short`, `git log --oneline`, a tracked-file secret scan, and a search proving that payment operations are absent from executable code.

- [ ] **Step 2: Request an independent code and skill review**

Ask a fresh reviewer to compare the implementation to the design and plan, prioritizing secret exposure, duplicate orders, ambiguous timeouts, approval bypasses, and accidental payment behavior. Fix confirmed findings with failing regression tests first.

- [ ] **Step 3: Verify GitHub identity and repository-name availability**

Run: `gh auth status` and `gh repo view savage-miniapp-openapi`

Expected: GitHub authentication is active and the target name is available, or an existing repository is confirmed as the intended destination.

- [ ] **Step 4: Create and push the public repository**

Run: `gh repo create savage-miniapp-openapi --public --source . --remote origin --push`

Expected: the repository is public, `main` is pushed, and no secret appears in the remote tree.

- [ ] **Step 5: Verify the public artifact**

Run: `gh repo view --json nameWithOwner,url,visibility,defaultBranchRef` and inspect the remote Actions state. Confirm `visibility` is `PUBLIC`, the default branch is `main`, and validation completes successfully.

- [ ] **Step 6: Report the release**

Provide the public repository URL, local repository link, verification summary, installation command, and the statement that no live booking or payment request was made during tests.
