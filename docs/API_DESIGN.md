# API Architecture & Contract Specification
## ResumeMatch: RESTful OpenAPI v1 Specification

---

## 1. API Architecture Principles

The ResumeMatch API is designed around strict RESTful conventions, clear resource boundaries, explicit Pydantic v2 schemas, and standard HTTP semantics:
1. **URI Versioning**: All production endpoints are prefixed with `/api/v1`.
2. **Predictable JSON Envelopes**: Consistent error and success structures across all routes.
3. **Strict Validation**: Request validation is handled declaratively via Pydantic v2, returning structured 422 responses on schema violations.
4. **Idempotence & Safety**: Safe methods (`GET`, `HEAD`, `OPTIONS`) never mutate state. State deletions (`DELETE`) are idempotent.
5. **Interactive OpenAPI Documentation**: Automatic documentation exposed at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## 2. Authentication & Authorization

Protected endpoints require a cryptographic Bearer token passed in the HTTP `Authorization` header:
```http
Authorization: Bearer <jwt_access_token>
```
- **Token Algorithm**: HMAC-SHA256 (`HS256`).
- **Token Payload**: Contains `sub` (User UUID), `exp` (Expiry timestamp, 60 minutes), and `type` (`access`).
- **401 Unauthorized**: Returned for missing, expired, or tampered tokens.
- **403 Forbidden**: Returned if a user attempts to access or delete another user's resume or match record.

---

## 3. Global Error Response Envelope

Every non-2xx response follows a unified error schema:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resume does not exist or has been deleted.",
    "details": [
      {
        "field": "resume_id",
        "issue": "UUID 550e8400-e29b-41d4-a716-446655440000 not found"
      }
    ]
  },
  "timestamp": "2026-10-08T23:30:00Z",
  "request_id": "req_8f12a4b9"
}
```

---

## 4. Endpoint Specifications

### 4.1 Authentication Module (`/api/v1/auth`)

#### `POST /api/v1/auth/register`
Creates a new user account.
- **Request Body (`application/json`)**:
  ```json
  {
    "email": "candidate@example.com",
    "password": "StrongPassword123!",
    "full_name": "Jane Doe"
  }
  ```
- **Responses**:
  - `201 Created`: Returns user profile and initial access token.
  - `400 Bad Request`: Email already registered.
  - `422 Unprocessable Entity`: Password fails complexity rules (<8 chars).

#### `POST /api/v1/auth/login`
Authenticates user credentials and issues a JWT token.
- **Request Body (`application/json`)**:
  ```json
  {
    "email": "candidate@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
      "token_type": "bearer",
      "expires_in": 3600,
      "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "candidate@example.com",
        "full_name": "Jane Doe"
      }
    }
    ```
  - `401 Unauthorized`: Invalid email or password.

#### `GET /api/v1/auth/me`
Retrieves authenticated user profile.
- **Headers**: `Authorization: Bearer <token>`
- **Responses**: `200 OK` (User schema).

---

### 4.2 Resume Module (`/api/v1/resumes`)

#### `POST /api/v1/resumes/upload`
Uploads and parses a candidate resume PDF.
- **Headers**: `Authorization: Bearer <token>`, `Content-Type: multipart/form-data`
- **Form Data**:
  - `file`: PDF binary (max 5 MB).
- **Processing**:
  1. Validates magic bytes (`%PDF-`).
  2. Runs PyMuPDF text and section extraction.
  3. Runs NLP entity extraction (skills, experience years, education).
  4. Generates 384-d semantic embedding.
  5. Persists to PostgreSQL `resumes` table.
- **Response (`201 Created`)**:
  ```json
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "original_filename": "Jane_Doe_Resume.pdf",
    "file_size_bytes": 142050,
    "parsed_data": {
      "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "PyTorch"],
      "experience_years": 5.5,
      "education_level": "Bachelor's",
      "education_details": "B.S. in Computer Science, 2019",
      "sections_detected": ["Summary", "Skills", "Experience", "Education"]
    },
    "created_at": "2026-10-08T23:35:00Z"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Invalid file format (non-PDF).
  - `413 Payload Too Large`: File exceeds 5 MB.
  - `422 Unprocessable Entity`: Corrupted or password-protected PDF.

#### `GET /api/v1/resumes`
Retrieves paginated list of user's resumes.
- **Parameters**: `skip` (default 0), `limit` (default 20).
- **Response (`200 OK`)**: List of resume summaries.

#### `GET /api/v1/resumes/{id}`
Retrieves full details of a specific resume.
- **Response (`200 OK`)**: Complete resume details and structured data.
- **Error (`404 Not Found`)**: Resume ID does not exist or unauthorized.

#### `DELETE /api/v1/resumes/{id}`
Hard deletes a resume, its parsed text, vector embeddings, and all matching records.
- **Response (`204 No Content`)**: Successfully purged with zero residues.
- **Error (`404 Not Found`)**: Resume ID not found.

---

### 4.3 Job Module (`/api/v1/jobs`)

#### `POST /api/v1/jobs/analyze`
Ingests and parses a job description text to extract requirements.
- **Request Body (`application/json`)**:
  ```json
  {
    "title": "Senior Backend Engineer",
    "company": "Acme Cloud Corp",
    "raw_text": "We are looking for a Senior Backend Engineer with 5+ years of Python experience..."
  }
  ```
- **Response (`200 OK` / `201 Created`)**:
  ```json
  {
    "id": "789e0123-e89b-12d3-a456-426614174999",
    "title": "Senior Backend Engineer",
    "company": "Acme Cloud Corp",
    "structured_requirements": {
      "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
      "preferred_skills": ["Kubernetes", "Redis", "AWS"],
      "minimum_experience_years": 5.0,
      "minimum_education_level": "Bachelor's"
    }
  }
  ```

---

### 4.4 Matching & Scoring Engine (`/api/v1/match`)

#### `POST /api/v1/match`
Executes hybrid matching between a resume and job description. Supports both saved IDs and direct on-the-fly execution.
- **Request Body (`application/json`)**:
  ```json
  {
    "resume_id": "123e4567-e89b-12d3-a456-426614174000",
    "job_text": "We are seeking a Senior Backend Engineer...",
    "job_title": "Senior Backend Engineer",
    "save_result": true
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "match_id": "999e4567-e89b-12d3-a456-426614174888",
    "overall_score": 87.2,
    "fit_category": "STRONG_MATCH",
    "sub_scores": {
      "semantic_score": 84.0,
      "skills_score": 92.5,
      "experience_score": 100.0,
      "education_score": 85.0
    },
    "score_weights": {
      "semantic": 0.35,
      "skills": 0.40,
      "experience": 0.15,
      "education": 0.10
    },
    "skills_breakdown": {
      "matched_required": ["Python", "FastAPI", "PostgreSQL", "Docker"],
      "matched_preferred": ["Redis"],
      "missing_critical": ["AWS"],
      "missing_preferred": ["Kubernetes"]
    },
    "experience_breakdown": {
      "candidate_years": 5.5,
      "required_years": 5.0,
      "delta_years": 0.5,
      "status": "MEETS_REQUIREMENT"
    },
    "education_breakdown": {
      "candidate_level": "Bachelor's",
      "required_level": "Bachelor's",
      "status": "FULLY_ALIGNED"
    },
    "explanation": {
      "summary": "High alignment for Senior Backend Engineer with exceptional skill overlap.",
      "key_strengths": [
        "Candidate meets 100% of required technical competencies.",
        "5.5 years of experience exceeds the 5.0-year threshold."
      ],
      "growth_areas": [
        "Lacks demonstrated AWS infrastructure experience."
      ]
    },
    "created_at": "2026-10-08T23:36:00Z"
  }
  ```

#### `GET /api/v1/match/history`
Returns historical match evaluations for the authenticated user with filtering and pagination.

#### `GET /api/v1/match/{id}`
Fetches the detailed diagnostics and explainability report of a previous match run.

---

### 4.5 Skill Taxonomy Module (`/api/v1/skills`)

#### `GET /api/v1/skills/taxonomy`
Allows client search and auto-completion against the canonical skill ontology.
- **Query Params**: `query=pyth`, `category=Languages`, `limit=10`.
- **Response (`200 OK`)**:
  ```json
  [
    {
      "canonical_name": "Python",
      "category": "Languages",
      "aliases": ["py", "python3", "python 3.x"]
    }
  ]
  ```
