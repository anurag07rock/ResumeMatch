# ResumeMatch

> **Explainable AI-Powered Resume-to-Job Matching Platform**

---

## ⚠️ Development Status
**Current State**: **Phase 2: Database Foundation (Active Milestone)**  
*The database foundation (SQLAlchemy 2.0 ORM models, pgvector type integration, Alembic migrations, session management, and repository layer) has been implemented. However, execution of live database migrations and integration tests is currently blocked pending Docker Desktop / PostgreSQL availability on the host machine.*

---

## 📖 Overview
ResumeMatch is a full-stack, explainable AI platform designed to match candidate resumes with job descriptions. Unlike black-box screening systems or naive keyword matchers, ResumeMatch combines:
- **Dense Semantic Embeddings** (`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions)
- **Deterministic Skill Ontology Matching** (1,200+ canonical technical skills)
- **Experience Timeline Verification** (Interval parsing and delta scoring)
- **Education Hierarchy Classification**
- **Explainable Attribution & Diagnostics** (Transparent sub-scores, gap analysis, and natural-language justifications)

---

## 🗄️ Database Architecture & Requirements

### Core Database Stack
- **Engine**: **PostgreSQL 16** with **`pgvector`** extension.
- **ORM / Driver**: **SQLAlchemy 2.x** with **`asyncpg`** async driver.
- **Migrations**: **Alembic** (versioned in `backend/alembic/versions/`).
- **Vector Columns**: 384-dimensional dense vectors (`vector(384)`) on `resumes` and `jobs`.
- **Referential Integrity**: Cascading deletes (`ON DELETE CASCADE`) enforcing privacy and GDPR right-to-be-forgotten.

### Entities Implemented in Foundation
1. **`users`** (`User`): Authentication identity, roles, timestamps.
2. **`resumes`** (`Resume`): Candidate text, structured JSONB data, 384-d vector embeddings (`Vector(384)`).
3. **`jobs`** (`Job`): Target position, raw text, structured requirements JSONB, 384-d vector embeddings (`Vector(384)`).
4. **`matches`** (`Match`): Composite & sub-scores (skills, semantic, exp, edu), breakdown & explanation payloads.
5. **`skill_taxonomy`** (`SkillTaxonomy`): Canonical skills, category classifications, and alias arrays (`TEXT[]`).

---

## 🐳 Docker Desktop & Database Setup

To run the local PostgreSQL 16 + pgvector development database:

1. **Install and Launch Docker Desktop**:
   - If not installed, download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop).
   - Ensure the Docker daemon is running.

2. **Start Development Database**:
   ```powershell
   # From repository root
   docker compose up -d db
   ```

3. **Verify Database Container**:
   ```powershell
   docker compose ps
   ```

---

## ⚙️ Environment Configuration

Copy the environment template:
```powershell
cp .env.example .env
```

Key database settings in `.env`:
```ini
DATABASE_PROFILE=postgres_pgvector
DATABASE_URL="postgresql+asyncpg://resumematch_user:resumematch_password@localhost:5432/resumematch"
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=resumematch_user
POSTGRES_PASSWORD=resumematch_password
POSTGRES_DB=resumematch
```

---

## 🚀 Migration & Database Commands

### Run Alembic Migrations
```powershell
# From repository root
backend\venv\Scripts\alembic.exe upgrade head

# Or from backend/ directory
cd backend
.\venv\Scripts\alembic upgrade head
```

### Run Database Integration Tests
```powershell
# Strictly executes against live PostgreSQL + pgvector
backend\venv\Scripts\pytest.exe backend\tests\test_db_postgres.py -v
```

---

## 🚀 Local Service Startup

### Backend (FastAPI)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```
- Health Check: [http://localhost:8000/health](http://localhost:8000/health) (Service status)
- Database Health Check: [http://localhost:8000/health/db](http://localhost:8000/health/db) (DB connectivity status)
- OpenAPI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend (Next.js 16)
```powershell
cd frontend
npm run dev
```
- Web Application: [http://localhost:3000](http://localhost:3000)

---

## 🏛️ Architecture & Governance
- Engineering Governance & Rules: [`AGENTS.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/AGENTS.md)
- Database Specification: [`docs/DATABASE_DESIGN.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/DATABASE_DESIGN.md)
- AI/ML Architecture: [`docs/AI_ML_ARCHITECTURE.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/AI_ML_ARCHITECTURE.md)
- Security Specification: [`docs/SECURITY.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/SECURITY.md)
