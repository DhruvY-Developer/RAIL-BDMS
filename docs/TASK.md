---

# `TASKS.md`

```markdown
# Step-by-Step Implementation Roadmap & Agent Tasks
## Build Plan: Rail-BDMS Engineering Workflow

This task sequence is optimized for autonomous and semi-autonomous coding agents. Every task is atomic, has concrete inputs and outputs, and contains a strict verification check.

---

### Phase 1: Project Scaffolding & Core Architecture Setup

- [ ] **TASK-101: Scaffold Backend Service & Directory Layout**
  - **Goal**: Initialize Python 3.11+ FastAPI application with modular layout, Pydantic v2 settings, and pre-commit linters.
  - **Inputs**: Directory tree from `ARCHITECTURE.md`.
  - **Outputs**: `backend/app/main.py`, `backend/app/core/config.py`, `backend/requirements.txt`.
  - **Verification**: Run `uvicorn app.main:app --reload` and verify `GET /docs` returns 200 OK.

- [ ] **TASK-102: Configure PostgreSQL + PostGIS Database & SQLAlchemy 2.0 Base**
  - **Goal**: Establish async database engine, Alembic migration environment, and PostGIS extension loading.
  - **Inputs**: DDL schemas from `ARCHITECTURE.md`.
  - **Outputs**: `backend/app/db/session.py`, `backend/app/db/base.py`, `backend/alembic/env.py`.
  - **Verification**: Run `alembic upgrade head` and verify tables exist via `psql -c "\dt"`.

- [ ] **TASK-103: Scaffold Control Office React + TypeScript Application**
  - **Goal**: Initialize Vite React application with MUI v5, TailwindCSS, TanStack Query, and Zustand.
  - **Inputs**: `frontend/` directory structure.
  - **Outputs**: `frontend/package.json`, `frontend/src/App.tsx`, `frontend/vite.config.ts`.
  - **Verification**: Run `npm run build` and ensure zero TypeScript errors.

---

### Phase 2: Ingestion, Identity Resolution & Data Layer

- [ ] **TASK-201: Implement Canonical Data Models & Pydantic Schemas**
  - **Goal**: Build ORM entities and validation schemas for Assets, Tasks, Corridor Windows, and Train Movements.
  - **Inputs**: `ARCHITECTURE.md` Section 3.
  - **Outputs**: `backend/app/db/models/*.py`, `backend/app/schemas/*.py`.
  - **Verification**: Unit test schema validation with valid and invalid payload fixtures in `tests/test_schemas.py`.

- [ ] **TASK-202: Build TMS, SMMS, TDMS & COA Synthetic Data Generators**
  - **Goal**: Create realistic Indian Railways synthetic datasets covering a sample busy division (e.g., Delhi-Palwal, 10 stations, 150 assets, 40 train paths, 80 defect demands).
  - **Inputs**: Railway domain rules for chainage, signals, turnouts, and OHE masts.
  - **Outputs**: `backend/app/services/ingestion/mock_data_generator.py`.
  - **Verification**: Execute script to output mock JSON files; check that all mandatory fields are populated.

- [ ] **TASK-203: Implement Asset Identity Resolution Engine**
  - **Goal**: Code the 4-tier deterministic matching algorithm to link disparate TMS/SMMS/TDMS asset IDs to canonical records.
  - **Inputs**: `PRD.md` FR-2 requirements.
  - **Outputs**: `backend/app/services/identity/resolver.py`, `backend/app/services/identity/spatial_matcher.py`.
  - **Verification**: Run test cases resolving mismatched IDs: exact match returns 1.0, chainage overlap $>90\%$ returns $\ge 0.90$, ambiguity routes to `UNRESOLVED_IDENTITY`.

---

### Phase 3: Analytics, Priority Scoring & Compatibility Engine

- [ ] **TASK-301: Implement Explainable Priority Scoring Engine**
  - **Goal**: Program the Criticality, Urgency, and Composite Priority scoring mathematical formulas with natural language explanations.
  - **Inputs**: `PRD.md` FR-3 equations.
  - **Outputs**: `backend/app/services/analytics/priority_engine.py`.
  - **Verification**: Pytest asserting that an overdue safety-critical track defect on an HDN route scores higher than a routine siding inspection, returning an explanation string.

- [ ] **TASK-302: Implement Quantile Duration & Overrun Risk Predictor**
  - **Goal**: Implement fallback quantile regressors and XGBoost overrun classifiers predicting P50, P80, P95 durations from historical task performance.
  - **Inputs**: Historical execution log features (asset class, department, machine type, crew ID, season).
  - **Outputs**: `backend/app/services/analytics/duration_estimator.py`, `backend/app/services/analytics/overrun_predictor.py`.
  - **Verification**: Execute evaluation test ensuring predicted P95 duration $\ge$ P80 duration $\ge$ P50 duration.

- [ ] **TASK-303: Build Shadow Block Compatibility Graph Engine**
  - **Goal**: Formulate network graph of pending tasks; evaluate edge connectivity based on spatial overlap, line/road matching, and isolation compatibility.
  - **Inputs**: `PRD.md` FR-4 compatibility rules.
  - **Outputs**: `backend/app/services/optimizer/compatibility_graph.py`.
  - **Verification**: Provide 3 compatible tasks (Track tamping + OHE inspection + S&T bond check on same line) $\to$ returns single consolidated cluster. Incompatible tasks (opposing isolations) remain separate.

---

### Phase 4: Google OR-Tools CP-SAT Mathematical Solver

- [ ] **TASK-401: Implement Core CP-SAT Block Scheduling Model**
  - **Goal**: Construct integer programming model using Google OR-Tools CP-SAT enforcing hard timetable envelopes, window boundaries, machine exclusivity, and multi-department objective optimization.
  - **Inputs**: Mathematical formulation in `ARCHITECTURE.md` Section 4.
  - **Outputs**: `backend/app/services/optimizer/cpsat_scheduler.py`, `constraints.py`, `objectives.py`.
  - **Verification**: Run solver against a test scenario with 20 tasks and 10 train paths; assert zero timetable overlap and solver returns `OPTIMAL` or `FEASIBLE`.

- [ ] **TASK-402: Implement Timetable Protection Certifier**
  - **Goal**: Create standalone verification pass that validates the output plan against the Working Time Table (WTT), checking headways and emitting a signed SHA-256 certificate JSON.
  - **Inputs**: Solved schedule assignments + `train_movements` table.
  - **Outputs**: `backend/app/services/optimizer/certifier.py`.
  - **Verification**: Introduce an intentional artificial overlap in a test; verify that the certifier detects the clash, throws `TimetableViolationException`, and refuses certificate generation.

- [ ] **TASK-403: Implement Multi-Horizon Rolling Optimization Orchestrator**
  - **Goal**: Build horizon coordinator handling 26-week strategic reservations, 4-week rolling assignments, 1-week execution freezes, and next-day real-time delta re-optimization.
  - **Inputs**: `PRD.md` FR-6 specifications.
  - **Outputs**: `backend/app/services/optimizer/horizon_orchestrator.py`.
  - **Verification**: Test 24-hour freeze logic: frozen tasks must retain fixed start/end timestamps during a re-solve run.

---

### Phase 5: REST APIs & Asynchronous Job Pipeline

- [ ] **TASK-501: Implement REST Endpoints for Tasks, Assets & Corridors**
  - **Goal**: Expose CRUD and filtering endpoints for maintenance demands, canonical assets, and timetable corridor slots.
  - **Inputs**: FastAPI routers, Pydantic schemas.
  - **Outputs**: `backend/app/api/v1/endpoints/tasks.py`, `assets.py`, `corridors.py`.
  - **Verification**: Execute integration tests in `tests/test_api.py` validating status codes, filtering, and pagination.

- [ ] **TASK-502: Implement Optimization Orchestration Endpoints with Celery**
  - **Goal**: Build async background job trigger for solver execution with progress polling and plan retrieval.
  - **Inputs**: Celery worker setup, Redis broker.
  - **Outputs**: `backend/app/api/v1/endpoints/optimizer.py`, `backend/app/services/optimizer/tasks.py`.
  - **Verification**: Post to `/api/v1/optimizer/solve`, retrieve `job_id`, poll status until `SUCCESS`, and fetch resulting plan payload.

- [ ] **TASK-503: Implement Execution Cockpit WebSocket & State Machine Endpoints**
  - **Goal**: Create real-time state transition API (`REQUESTED` $\to$ `GRANTED` $\to$ `PROTECTION_APPLIED` $\to$ `CLOSED`) with WebSocket broadcasts for live field updates.
  - **Inputs**: Block state machine specification.
  - **Outputs**: `backend/app/api/v1/endpoints/execution.py`, WebSocket handler.
  - **Verification**: Connect test WebSocket client, trigger state update, and verify real-time event reception.

---

### Phase 6: Control Office UI Development (React + TypeScript)

- [ ] **TASK-601: Build Executive Command Center & KPI Metrics View**
  - **Goal**: Create top-level dashboard with active block cards, corridor utilization gauges, timetable conflict counters, and overdue critical task lists.
  - **Inputs**: ECharts, MUI components.
  - **Outputs**: `frontend/src/components/command_center/Dashboard.tsx`.
  - **Verification**: Render dashboard with mock API data; verify responsive layout and correct numerical calculations.

- [ ] **TASK-602: Build Interactive Train-Path & Maintenance Gantt Timeline**
  - **Goal**: Implement dual-layer timeline using `vis-timeline` displaying scheduled train paths alongside granted and shadow maintenance blocks.
  - **Inputs**: Block plan API data + Train movement schedule.
  - **Outputs**: `frontend/src/components/gantt/ScheduleGantt.tsx`.
  - **Verification**: Visually confirm distinct color coding: trains (green/blue), single-dept blocks (amber), shadow blocks (purple), and conflicts (red).

- [ ] **TASK-603: Build Shadow Block Planner Workbench & What-If Sandbox**
  - **Goal**: Create interactive workspace allowing controllers to drag-and-drop tasks into shadow groups, adjust buffer durations, and trigger sandbox solver re-runs.
  - **Inputs**: Planner Workbench UI specs.
  - **Outputs**: `frontend/src/components/shadow_workbench/PlannerWorkbench.tsx`.
  - **Verification**: Move a task in the UI, trigger "What-If" recalculation, and verify updated corridor savings and certificate status.

- [ ] **TASK-604: Build Geospatial Division Map View**
  - **Goal**: Implement Leaflet/OpenLayers GIS map showing section topology, real-time block locations, and asset defect hotspots.
  - **Inputs**: GeoJSON section topology.
  - **Outputs**: `frontend/src/components/map/SectionMap.tsx`.
  - **Verification**: Map renders track sections with interactive popups detailing active blocks and asset status.

---

### Phase 7: Depot In-Charge Mobile PWA

- [ ] **TASK-701: Scaffold Offline-First Depot PWA with IndexedDB**
  - **Goal**: Build lightweight, responsive PWA for field Senior Section Engineers with local cache persistence.
  - **Inputs**: `depot-pwa/` workspace setup.
  - **Outputs**: `depot-pwa/src/db/indexedDb.ts`, Service Worker registration.
  - **Verification**: Disconnect network in browser DevTools; verify task queue loads from local IndexedDB cache.

- [ ] **TASK-702: Build Pre-Work Readiness Checklist & Live Execution Logger**
  - **Goal**: Implement interactive checklist (crew, machine, permit, isolation) and one-touch timestamp capture (`START`, `RESTORED`, `CLOSED`) with photo upload support.
  - **Inputs**: Field execution workflow rules.
  - **Outputs**: `depot-pwa/src/pages/ReadinessChecklist.tsx`, `CompletionCapture.tsx`.
  - **Verification**: Submit checklist offline, reconnect network, and verify queued events sync to backend API.

---

### Phase 8: End-to-End Integration, Validation & Benchmarking

- [ ] **TASK-801: Execute Full Simulation Benchmark on Real Division Scenario**
  - **Goal**: Run end-to-end integration test: ingest 100 demands, resolve assets, compute priorities, optimize weekly plan with shadow block grouping, and verify zero timetable conflicts.
  - **Inputs**: Full synthetic benchmark dataset.
  - **Outputs**: `tests/benchmark_e2e_simulation.py`.
  - **Verification**: Assert:
    1. Timetable conflicts == 0.
    2. Shadow block ratio $\ge 30\%$.
    3. Corridor utilization increase $\ge 25\%$ vs baseline.
    4. Solver execution time $\le 30\text{ seconds}$.