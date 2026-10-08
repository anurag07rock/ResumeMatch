# ResumeMatch Backend

FastAPI microservice for ResumeMatch: Explainable AI-Powered Resume-to-Job Matching Platform.

---

## Current Status
**Phase 1: Environment & Repository Scaffolding**
The backend currently provides a foundation service with health-check monitoring. Application logic, parsers, and vector models will be integrated in subsequent phases.

---

## Requirements
- Python 3.11 (`py -3.11`)
- Virtual environment (`venv/`)

---

## Local Development Setup

1. **Activate Virtual Environment**:
   ```powershell
   # Windows PowerShell
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Run Development Server**:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

4. **Verify Health Endpoint**:
   ```powershell
   curl http://localhost:8000/health
   ```

5. **Run Test Suite**:
   ```powershell
   pytest tests/
   ```
