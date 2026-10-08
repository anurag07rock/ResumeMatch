# AGENTS.md — Engineering Rules & Project Governance
## ResumeMatch: Explainable AI-Powered Resume-to-Job Matching Platform

This document defines the strict engineering governance, architectural constraints, quality standards, and operational rules for the **ResumeMatch** repository. All contributors and AI agents working on this codebase must adhere strictly to these rules.

---

## 1. Architecture
- **Follow Approved Documents**: Adhere strictly to the approved architecture specifications in [`/docs`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs).
- **No Unapproved Structural Shifts**: Do not make major architectural modifications without explicit prior approval.
- **Strict Separation of Concerns**: Keep frontend, backend, database persistence, AI/ML inference, and infrastructure components decoupled with clean boundaries.
- **Modularity & Testability**: Prefer modular, decoupled components that can be tested in complete isolation without network or external system dependencies.

---

## 2. Type Safety
- **Frontend**: Enforce TypeScript strict mode (`"strict": true` in `tsconfig.json`). Prohibit arbitrary use of `any` types.
- **Backend**: Strict Python type hints across all production code, validated by `mypy` and runtime Pydantic v2 schemas.
- **Schema Contracts**: All API inputs, outputs, query parameters, and error responses must be governed by typed Pydantic models.
- **Contract Parity**: Maintain 1-to-1 parity between frontend TypeScript interface definitions and backend Pydantic schemas to avoid serialization mismatches.

---

## 3. API Contracts & Canonical Field Names
All endpoints, schemas, and diagnostics must strictly use the following canonical field names:
- `skills_breakdown`
- `experience_breakdown`
- `education_breakdown`
- `explanation`

**Prohibited Alternatives**: Do not introduce alternative field names such as:
- `skills_analysis`
- `structured_requirements`
- `explanation_narrative`
unless explicitly justified, documented, and approved.

---

## 4. Database
- **Follow Specifications**: Adhere to [`docs/DATABASE_DESIGN.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/DATABASE_DESIGN.md).
- **Referential Integrity**: Always enforce relational foreign key constraints and cascade delete rules (`ON DELETE CASCADE`).
- **Data Access Boundary**: Never bypass the repository/data-access layer or write raw SQL directly in API route handlers.
- **Schema Alignment**: Do not permit schema drift between SQLAlchemy ORM models, Alembic migrations, and Pydantic API schemas.
- **Job Ingestion Mapping**: Inline job descriptions submitted on-the-fly for matching must map cleanly to a persisted `Job` record in the database.

---

## 5. AI/ML Engineering
- **Modular & Testable**: All AI/ML logic (parsers, tokenizers, embedding wrappers, scoring engines) must be modular and independently testable without loading the web server.
- **Zero Fabrication**: Never fabricate, hallucinate, or extrapolate resume or job information.
- **Zero Invention**: Never invent skills, experience durations, degrees, institutions, certifications, or qualifications.
- **Deterministic Reproducibility**: Given the same resume text, job description, and configuration weights, scoring calculations must produce 100% identical results.
- **Metadata Tracking**: Explicitly record model names, versions, dimension counts, and scoring weights in evaluation and response payloads.
- **Lifecycle Efficiency**: The embedding model must be loaded into memory once during application startup (e.g., FastAPI lifespan) and never reloaded per request.
- **Document Chunking**: Long documents exceeding model sequence limits (512 tokens) must be handled through an explicit sliding-window chunking strategy with mean pooling, not naive truncation.
- **Evidence-Based Explanations**: Explanations must be derived strictly from calculated score data and verified entity intersections. Never expose hidden or unverified reasoning.

---

## 6. Security & Privacy
- **Zero Committed Secrets**: Never commit API keys, database credentials, JWT secrets, or certificates.
- **Environment Configuration**: Manage all sensitive settings strictly via environment variables (`.env`) loaded through Pydantic `BaseSettings`.
- **Input Validation**: Validate every user-supplied input on both client and server boundaries against malicious payloads, XSS, and SQL injection.
- **File Upload Hardening**: Validate all uploaded files by MIME type, maximum size ($\le 5\text{ MB}$), and file signature / magic bytes (`%PDF-`). Never execute uploaded files.
- **Authentication & Authorization**: Strictly enforce JWT authentication and tenant-level authorization. Users may only access, query, or delete their own resumes, jobs, matches, and profile data.
- **PII Minimization**: Sanitize logs against PII leakage and offer optional redaction pipelines.
- **GDPR Hard Deletion**: Strictly comply with [`docs/SECURITY.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/SECURITY.md): deleting a resume must immediately and permanently purge all parsed text, structured data, vectors, and match records.

---

## 7. Error Handling & Observability
- **Structured Error Responses**: All non-2xx responses must return a standardized JSON error envelope containing `error.code`, `error.message`, and contextual `details`.
- **No Swallowed Exceptions**: Never use bare `except:` or silently suppress errors. Log tracebacks with request correlation IDs.
- **No Mock / Fake Scores on Failure**: If parsing, vector embedding, or scoring fails, raise an explicit structured error. Never return mock, random, or default scores to mask system failures.
- **Meaningful Diagnostics**: Return informative HTTP status codes and diagnostics for corrupted PDFs (422), oversized files (413), missing entities (404), unauthorized access (401/403), or offline models (503).

---

## 8. Testing & Quality Assurance
- **Comprehensive Coverage**: New backend business logic and endpoints require corresponding unit and integration tests.
- **Deterministic Math Tests**: All scoring algorithms, weight calculations, and boundary conditions ($0\%$, $100\%$, missing values) require automated unit assertions.
- **API Contract Tests**: API routes must be covered by integration tests using `httpx.AsyncClient`.
- **Frontend & E2E Validation**: Critical user flows (auth, file upload, match dashboard, deletion) must be validated with Playwright E2E tests.
- **Integrity Rule**: Never claim a task is completed if required tests fail or have not been executed.

---

## 9. Documentation
- **Keep Current**: Update relevant `/docs` specifications whenever an approved architectural or schema change occurs.
- **Accurate Reference**: Keep `README.md` and API specifications aligned with actual implementation.
- **Zero Ghost Documentation**: Never document features, endpoints, or flags that do not actually exist in the codebase.

---

## 10. Code Quality & Simplicity
- **Simplicity First**: Prefer straightforward, readable, and maintainable solutions over speculative over-engineering.
- **Zero Redundant Abstractions**: Avoid premature abstraction layers and duplicate business logic.
- **Focused Scope**: Maintain single-responsibility classes and functions.
- **Meaningful Names**: Use descriptive, domain-aligned identifiers.
- **Minimal Dependencies**: Do not introduce external libraries or dependencies without explicit architectural justification.

---

## 11. Development Workflow & Task Reporting
Every completed phase and milestone must conclude with a mandatory **Task Completion Report** formatted with the following exact schema:

```markdown
### 📋 Task Completion Report
- **Implementation Summary**: Brief narrative of what was executed.
- **Files Created**: List of all created file paths.
- **Files Modified**: List of all modified file paths.
- **Dependencies Added**: List of packages installed or specified.
- **Database Changes**: Schema updates, migrations, or DDL operations.
- **API Changes**: Endpoints added, modified, or removed.
- **Tests Run**: List of test suites executed.
- **Tests Passed/Failed**: Count of passing and failing tests.
- **Verification Performed**: Manual or automated verification steps taken.
- **Known Issues**: Unresolved defects or technical debt noted.
- **Manual Actions Required**: Actions the user needs to perform.
- **Architectural Decisions**: Rationale for design choices made during the phase.
- **Next Recommended Step**: Immediate subsequent milestone.
```
*Rule: Never claim successful completion if verification or tests failed.*

---

## 12. Phase Discipline
- **Strict Scope Boundaries**: Implement only the explicitly assigned phase. Do not silently implement future phases.
- **Document, Don't Pre-Implement**: If an unanticipated future requirement is uncovered, document it in `/docs` rather than implementing it prematurely.
- **Verify Before Advancing**: Validate the current phase completely before proceeding to subsequent milestones.

---

## 13. Portfolio Excellence & Authenticity
- **Clear & Understandable**: The codebase must be easily navigable and readable by technical recruiters, hiring managers, and peer engineers.
- **Zero Fake / Mock AI**: The matching and embedding engine must execute genuine neural embeddings and deterministic extraction—never hardcoded or canned scores.
- **Honest Differentiation**: Clearly distinguish sample/demo test fixtures from live user-uploaded records.
- **Truth in Documentation**: Accurately describe model architectures, benchmarks, and capabilities without inflating or exaggerating performance claims.
