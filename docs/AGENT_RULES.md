# AI Agent Instructions & Engineering Guardrails
## Domain: Indian Railways Block Demand Management System (Rail-BDMS)

### 1. Fundamental System Principles
1. **Human-in-the-Loop Supremacy**: Rail-BDMS is an advisory Decision Support System (DSS). NEVER write code that assumes direct control or issues commands to interlocking, electronic signalling, or traction SCADA systems. All optimization outputs are *proposals* awaiting human controller authorization.
2. **Absolute Safety Invariants as Hard Constraints**: Timetable protection, headway clearance buffers ($B_{\text{before}}, B_{\text{after}}$), and certified electrical/signalling isolations are strictly mathematical HARD constraints. NEVER convert a safety constraint into an objective penalty term or allow the solver to "trade off" safety for utilization.
3. **Deterministic & Explainable Outputs**: Every priority score, overrun risk estimate, and shadow block combination MUST include a human-readable explanation and parameter audit trail. Avoid opaque, unweighted end-to-end black-box architectures.

---

### 2. Code Quality & Language Conventions

#### Python / FastAPI Backend
* **Runtime**: Python 3.11+. Use strict typing everywhere (`from typing import Optional, List, Dict, Annotated`).
* **Framework**: FastAPI with Pydantic v2 schemas. Use `model_config = ConfigDict(from_attributes=True)` for ORM mapping.
* **SQLAlchemy**: Use SQLAlchemy 2.0 async syntax (`AsyncSession`, `select()`, `joinedload()`). Never use legacy query syntax (`session.query()`).
* **Database Field Types**: 
  * Primary keys must be `UUID` with `default=uuid.uuid4`.
  * All timestamp columns MUST be timezone-aware (`TIMESTAMP WITH TIME ZONE` or `DateTime(timezone=True)`).
  * Geospatial columns MUST use GeoAlchemy2 `Geometry(geometry_type, srid=4326)`.
* **Error Handling**: Throw domain-specific HTTPException classes (e.g., `TimetableConflictError`, `AssetMismatchError`) rather than raw generic 500 errors.

#### Optimization (Google OR-Tools CP-SAT)
* **Variable Bounds**: Always specify explicit, tight integer bounds for all CP-SAT `IntVar` and `IntervalVar` instances.
* **Time Discretization**: Model all continuous operational time in integer minutes from Unix epoch or planning horizon start ($t=0$).
* **Model Separation**: Keep constraint definitions (`constraints.py`), objective formulations (`objectives.py`), and model orchestration (`cpsat_scheduler.py`) in separated, modular files.
* **No Floating Point in CP-SAT**: CP-SAT requires integer coefficients. Scale all fractional weights (e.g., $0.55 \to 55$) and round consistently.

#### React / TypeScript Frontend
* **TypeScript**: Strict mode enabled (`"strict": true` in `tsconfig.json`). No `any` types allowed; define explicit interfaces in `types/`.
* **State Management**:
  * Server state: TanStack Query v5 (`useQuery`, `useMutation`).
  * Local UI state: Zustand stores.
* **Styling**: Material UI (MUI v5) coupled with TailwindCSS. Retain high-contrast scannability suitable for mission-critical Control Office displays.
* **Component Architecture**: Keep views modular (Gantt, Map, KPI Dashboard, Workbench). Always provide loading skeletons and explicit error boundaries.

---

### 3. Railway Domain Terminology Reference Guide
When generating variables, schemas, documentation, and UI labels, strictly adhere to authentic Indian Railways nomenclature:

| Term / Abbreviation | Definition & System Role |
|---|---|
| **TMS** | Track Management System (Civil Engineering / P-Way work orders and defects) |
| **SMMS** | Signalling Maintenance Management System (S&T points, signals, interlockings) |
| **TDMS** | Traction Distribution Management System (Electrical / TRD OHE power distribution) |
| **COA** | Control Office Application (Live train operations, paths, timetables, and delay logging) |
| **CTPC** | Chief Track Planning Controller (Officer managing division-wide maintenance blocks) |
| **Sr. DOM** | Senior Divisional Operations Manager (Operating department approving authority) |
| **SSE** | Senior Section Engineer (Field depot in-charge executing the maintenance work) |
| **RBP** | Rolling Block Plan (IR 26-week / 4-week / weekly maintenance planning framework) |
| **Shadow Block** | Multiple compatible tasks from different departments packed into one physical possession |
| **WTT** | Working Time Table (Official railway operational timetable baseline) |
| **OHE Isolation** | Switching off and earthing traction power supply for safe maintenance |
| **IMR / REM / OBS** | Rail defect severity classifications (Immediate Removal, Remedial, Observed) |

---

### 4. Agent Operational Guardrails
* **Context Preservation**: When creating or modifying modules, verify import integrity against the canonical directory structure in `ARCHITECTURE.md`.
* **No Placeholders in Logic**: Write complete, functional implementations. Do not emit stubbed functions like `pass  # TODO: implement solver logic`.
* **Unit Testing Requirement**: Every new service or mathematical routine must be accompanied by a comprehensive pytest module under `backend/tests/` validating normal execution and edge cases.