# ResumeMatch

> **Explainable AI-Powered Resume-to-Job Matching Platform**

---

## ⚠️ Development Status
**Current State**: **Phase 1: Environment & Repository Scaffolding (Active Development)**  
*This repository is currently under active foundational development and is not yet production-ready. Application features, parsers, neural embeddings, and database models will be implemented in subsequent development phases.*

---

## 📖 Overview
ResumeMatch is a full-stack, explainable AI platform designed to match candidate resumes with job descriptions. Unlike black-box screening systems or naive keyword matchers, ResumeMatch combines:
- **Dense Semantic Embeddings** (`sentence-transformers/all-MiniLM-L6-v2`)
- **Deterministic Skill Ontology Matching** (1,200+ canonical technical skills)
- **Experience Timeline Verification** (Interval parsing and delta scoring)
- **Education Hierarchy Classification**
- **Explainable Attribution & Diagnostics** (Transparent sub-scores, gap analysis, and natural-language justifications)

---

## 🛠️ Required Tool Versions

| Runtime / Tool | Required Version | Host Detected Version |
| :--- | :--- | :--- |
| **Python** | 3.11.x | Python 3.11.9 (`py -3.11`) |
| **Node.js** | 20.x or 24.x | v24.14.0 |
| **npm** | 10.x or 11.x | 11.9.0 |
| **Git** | 2.x+ | 2.54.0 |
| **Docker / Docker Compose** | Optional (for containerized DB) | Not running on host (Local SQLite fallback used) |
| **PostgreSQL + pgvector** | Optional (Production profile) | Optional for local Phase 1 |

---

## ⚙️ Environment Configuration

1. Copy the example configuration:
   ```bash
   cp .env.example .env
   ```
2. For local development without Docker, `DATABASE_PROFILE=local_sqlite` is configured by default.

---

## 🚀 Local Setup & Startup Instructions

### 1. Backend Setup (FastAPI + Python 3.11)

1. **Navigate to the backend directory and activate the virtual environment**:
   ```powershell
   # Windows PowerShell
   cd backend
   .\venv\Scripts\Activate.ps1
   ```

2. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Start the backend development server**:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

4. **Verify Health Endpoint**:
   - Web browser / cURL: [http://localhost:8000/health](http://localhost:8000/health)
   - Interactive OpenAPI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

5. **Run Backend Test Suite**:
   ```powershell
   pytest tests/
   ```

---

### 2. Frontend Setup (Next.js 15 + TypeScript)

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies** (if not already installed):
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```

4. **Access the web app**:
   - Navigate to [http://localhost:3000](http://localhost:3000)

5. **Run Linting & Type Checking**:
   ```bash
   npm run lint
   npx tsc --noEmit
   ```

---

## 🏛️ Architecture & Governance
- Engineering Governance & Rules: [`AGENTS.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/AGENTS.md)
- Product Requirements Document (PRD): [`docs/PRODUCT_REQUIREMENTS.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/PRODUCT_REQUIREMENTS.md)
- System Architecture: [`docs/ARCHITECTURE.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/ARCHITECTURE.md)
- AI/ML Architecture: [`docs/AI_ML_ARCHITECTURE.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/AI_ML_ARCHITECTURE.md)
- Database Design: [`docs/DATABASE_DESIGN.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/DATABASE_DESIGN.md)
- API Specification: [`docs/API_DESIGN.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/API_DESIGN.md)
- Security & Privacy: [`docs/SECURITY.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/SECURITY.md)
- Testing Strategy: [`docs/TESTING.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/TESTING.md)
- Development Roadmap: [`docs/ROADMAP.md`](file:///c:/Users/ap289/OneDrive/Desktop/RsmeMatch/docs/ROADMAP.md)
