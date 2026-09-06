# System Architecture & Technical Specifications
## Rail-BDMS: Scalable Multi-Horizon Optimization Platform

### 1. System Topology & Component Layout
 [EXTERNAL RAILWAY ECOSYSTEM]
                             TMS       SMMS      TDMS      COA
                              |          |         |        |
                              +----+-----+----+----+--------+
                                   | (REST / SFTP / Excel)
                                   v
+---------------------------------------------------------------------------------------------------+| RAIL-BDMS APPLICATION BOUNDARY                                                                    ||                                                                                                   ||  +---------------------------------------------------------------------------------------------+  ||  | INGESTION & NORMALIZATION LAYER                                                             |  ||  |  * Ingestion Adapters (TMSAdapter, SMMSAdapter, TDMSAdapter, COAAdapter)                     |  ||  |  * Schema Normalizer & Great Expectations Validator                                         |  ||  |  * Asset Identity Resolution Engine (Spatial PostGIS + String Distance Hierarchy)          |  ||  +----------------------------------------------+----------------------------------------------+  ||                                                 |                                                 ||                                                 v                                                 ||  +---------------------------------------------------------------------------------------------+  ||  | CANONICAL PERSISTENCE LAYER (PostgreSQL 16 + PostGIS + TimescaleDB)                         |  ||  |  * canonical_assets              * maintenance_tasks         * corridor_windows             |  ||  |  * train_movements               * resource_calendars        * block_plans                  |  ||  |  * identity_cross_references     * plan_audit_trail          * actual_execution_logs        |  ||  +----------------------------------------------+----------------------------------------------+  ||                                                 |                                                 ||                   +-----------------------------+-----------------------------+                   ||                   |                                                           |                   ||                   v                                                           v                   ||  +------------------------------------+       +------------------------------------------------+  ||  | ANALYTICS & PREDICTION ENGINE      |       | OPTIMIZATION & REASONING CORE                  |  ||  |  * Priority Scoring Engine         |       |  * Shadow Block Compatibility Graph Builder    |  ||  |  * Quantile Duration Estimator     |       |  * CP-SAT Mathematical Constraint Solver       |  ||  |  * Overrun Risk Classifier         |       |  * Timetable Protection Certifier Engine       |  ||  +-----------------+------------------+       +-----------------------+------------------------+  ||                    |                                                  |                           ||                    +----------------------------+---------------------+                           ||                                                 |                                                 ||                                                 v                                                 ||  +---------------------------------------------------------------------------------------------+  ||  | FASTAPI APPLICATION LAYER & ASYNC TASK ORCHESTRATION                                        |  ||  |  * REST Endpoints (/api/v1/*)           * WebSockets (/ws/execution-cockpit)               |  ||  |  * Celery / Redis Worker Pool          * Role-Based Access Control (Keycloak OIDC)          |  ||  +----------------------------------------------+----------------------------------------------+  ||                                                 |                                                 |+-------------------------------------------------|-------------------------------------------------+|+------------------------+------------------------+| (JSON / REST / WS)                              | (REST / Offline PWA)v                                                 v+----------------------------------------------+  +-----------------------------------------------+| CONTROL OFFICE WEB APP (React 18 + TS)       |  | DEPOT IN-CHARGE PWA (React + TS + IndexedDB)  ||  * Command Center & Geospatial Map (Leaflet) |  |  * Offline Task Queue & Work Execution Check  ||  * Interactive Timetable Gantt (vis-timeline)|  |  * Pre-Work Safety Checklist Sign-off         ||  * Shadow Block Workbench & What-If Sandbox  |  |  * Actual Timestamps & Photo Proof Capture    |+----------------------------------------------+  +-----------------------------------------------+
---

### 2. Tech Stack Matrix

| Layer | Component | Version / Library | Purpose |
|---|---|---|---|
| **Frontend** | Framework | React 18, TypeScript 5.4, Vite | Control Office Web App & Depot PWA |
| | UI Components | Material UI (MUI v5), TailwindCSS | Responsive layout, design system |
| | Visualizations | `vis-timeline` / Vis.js, Leaflet, Apache ECharts | Gantt timelines, geographic GIS, KPI charts |
| | Client State | TanStack Query v5, Zustand | Server caching, reactive local state |
| **Backend** | Runtime & API | Python 3.11+, FastAPI 0.110+ | High-performance asynchronous API layer |
| | Validation | Pydantic v2, Great Expectations | Strict data contract enforcement |
| | Async Workers | Celery 5.3+, Redis 7.2 | Asynchronous solver runs and batch ingestion |
| **Optimization & ML**| Constraint Solver | Google OR-Tools 9.9+ (CP-SAT) | Mathematical block scheduling |
| | Machine Learning | scikit-learn, LightGBM, XGBoost | Duration prediction, overrun risk estimation |
| **Database** | Core Database | PostgreSQL 16 + PostGIS 3.4 | Relational, spatial geometries, foreign keys |
| | Time Series | TimescaleDB Extension | High-frequency telemetry and execution logs |
| **Infra & Security** | Auth & Identity | Keycloak / OIDC | Enterprise SSO, fine-grained RBAC |
| | Observability | Prometheus, Grafana, OpenTelemetry | Solver telemetry, API metrics, audit logging |

---

### 3. Canonical Database Schema (PostgreSQL + PostGIS DDL)

```sql
-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Canonical Assets Table
CREATE TABLE canonical_assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(32) NOT NULL, -- 'TMS', 'SMMS', 'TDMS'
    source_asset_id VARCHAR(64) NOT NULL,
    asset_type VARCHAR(64) NOT NULL, -- 'TRACK_SEGMENT', 'TURNOUT', 'SIGNAL', 'OHE_MAST', 'TRANSFORMER'
    department VARCHAR(32) NOT NULL, -- 'ENGINEERING', 'S_AND_T', 'TRD'
    division VARCHAR(32) NOT NULL,
    section_id VARCHAR(64) NOT NULL,
    station_from VARCHAR(16) NOT NULL,
    station_to VARCHAR(16) NOT NULL,
    chainage_from NUMERIC(10, 3), -- Kilometer.Meter (e.g. 124.200)
    chainage_to NUMERIC(10, 3),
    line_or_road VARCHAR(32) NOT NULL, -- 'UP', 'DOWN', 'SL', 'ROAD_1'
    route_class VARCHAR(16) DEFAULT 'HDN', -- 'HDN', 'HUN', 'GROUP_A'
    criticality_class VARCHAR(16) DEFAULT 'CLASS_B', -- 'CLASS_A', 'CLASS_B', 'CLASS_C'
    location_geometry GEOMETRY(Geometry, 4326),
    parent_asset_id UUID REFERENCES canonical_assets(asset_id),
    status VARCHAR(32) DEFAULT 'OPERATIONAL',
    last_verified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_source_asset UNIQUE (source_system, source_asset_id)
);

CREATE INDEX idx_canonical_assets_section ON canonical_assets(section_id, line_or_road);
CREATE INDEX idx_canonical_assets_spatial ON canonical_assets USING GIST(location_geometry);

-- 2. Maintenance Tasks Table
CREATE TABLE maintenance_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(32) NOT NULL,
    source_task_id VARCHAR(64) NOT NULL,
    asset_id UUID NOT NULL REFERENCES canonical_assets(asset_id),
    department VARCHAR(32) NOT NULL,
    task_type VARCHAR(64) NOT NULL, -- 'PLAIN_TRACK_TAMPING', 'TURNOUT_RENEWAL', 'POINT_OVERHAUL', 'OHE_CANTILEVER_INSP'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    due_at TIMESTAMP WITH TIME ZONE NOT NULL,
    latest_completion_date TIMESTAMP WITH TIME ZONE NOT NULL,
    estimated_duration_min INT NOT NULL,
    min_duration_min INT NOT NULL,
    max_duration_min INT NOT NULL,
    requires_traffic_block BOOLEAN DEFAULT TRUE,
    requires_ohe_isolation BOOLEAN DEFAULT FALSE,
    requires_signal_disconnection BOOLEAN DEFAULT FALSE,
    requires_line_occupation BOOLEAN DEFAULT TRUE,
    required_crew_type VARCHAR(64),
    required_machine_type VARCHAR(64), -- 'CSM', 'BCM', 'UNIMAT', 'TOWER_WAGON', 'NONE'
    predecessor_task_ids UUID[] DEFAULT '{}',
    safety_class VARCHAR(32) DEFAULT 'SAFETY_CRITICAL', -- 'SAFETY_CRITICAL', 'OPERATIONAL_DEFECT', 'ROUTINE'
    status VARCHAR(32) DEFAULT 'PENDING' -- 'PENDING', 'VALIDATED', 'SCHEDULED', 'APPROVED', 'IN_PROGRESS', 'COMPLETED'
);

CREATE INDEX idx_tasks_due ON maintenance_tasks(due_at, status);
CREATE INDEX idx_tasks_asset ON maintenance_tasks(asset_id);

-- 3. Corridor Windows & Train Movements
CREATE TABLE corridor_windows (
    corridor_window_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id VARCHAR(64) NOT NULL,
    line_or_road VARCHAR(32) NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    available_duration_min INT GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (window_end - window_start))/60) STORED,
    allowed_block_type VARCHAR(32) DEFAULT 'MULTI_DEPARTMENT',
    confidence NUMERIC(4, 3) DEFAULT 1.000,
    timetable_version VARCHAR(32) NOT NULL
);

CREATE TABLE train_movements (
    movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    train_number VARCHAR(32) NOT NULL,
    service_date DATE NOT NULL,
    train_type VARCHAR(32) NOT NULL, -- 'PREMIUM_PASSENGER', 'EXPRESS', 'SUBURBAN', 'FREIGHT'
    origin VARCHAR(16) NOT NULL,
    destination VARCHAR(16) NOT NULL,
    section_id VARCHAR(64) NOT NULL,
    line_or_road VARCHAR(32) NOT NULL,
    planned_entry TIMESTAMP WITH TIME ZONE NOT NULL,
    planned_exit TIMESTAMP WITH TIME ZONE NOT NULL,
    min_clearance_before_min INT DEFAULT 15,
    min_clearance_after_min INT DEFAULT 15,
    priority_class INT DEFAULT 1 -- 1 (Highest, Vande Bharat/Rajdhani) to 5 (Empty Freight)
);

CREATE INDEX idx_train_movements_section_time ON train_movements(section_id, line_or_road, planned_entry, planned_exit);

-- 4. Block Plans & Shadow Groups
CREATE TABLE block_plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    horizon_type VARCHAR(32) NOT NULL, -- '26_WEEK', '4_WEEK', 'WEEKLY', 'NEXT_DAY'
    plan_version INT NOT NULL DEFAULT 1,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    solver_status VARCHAR(32) NOT NULL, -- 'OPTIMAL', 'FEASIBLE', 'INFEASIBLE'
    certificate_hash VARCHAR(64) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    approved_by VARCHAR(64),
    approved_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE scheduled_block_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES block_plans(plan_id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES maintenance_tasks(task_id),
    corridor_window_id UUID NOT NULL REFERENCES corridor_windows(corridor_window_id),
    block_group_id UUID, -- Shared ID if scheduled as a Shadow Block
    planned_start TIMESTAMP WITH TIME ZONE NOT NULL,
    planned_end TIMESTAMP WITH TIME ZONE NOT NULL,
    priority_score NUMERIC(5, 2) NOT NULL,
    lead_department VARCHAR(32) NOT NULL,
    approval_status VARCHAR(32) DEFAULT 'SUGGESTED',
    actual_start TIMESTAMP WITH TIME ZONE,
    actual_end TIMESTAMP WITH TIME ZONE,
    actual_output_value NUMERIC(10, 2),
    overrun_minutes INT DEFAULT 0,
    closure_reason TEXT
);
4. Mathematical Optimization Model (Google OR-Tools CP-SAT)4.1 Index Sets and Parameters$i \in \mathcal{T}$: Maintenance tasks pending execution.$w \in \mathcal{W}$: Timetable-approved candidate corridor windows.$g \in \mathcal{G}$: Candidate shadow block groups.$r \in \mathcal{R}$: Dedicated resources (specialized machines, crew depots).$t \in \mathcal{M}$: Scheduled train movements.$W_{s}(w), W_{e}(w)$: Start and end timestamps of corridor window $w$.$T_{s}(t), T_{e}(t)$: Entry and exit timestamps of train movement $t$.$B_{\text{before}}, B_{\text{after}}$: Pre- and post-train safety headway buffer times.$D_i$: Required duration of task $i$.$P_i$: Priority score of task $i$ ($0 \le P_i \le 100$).4.2 Decision Variables$s_i \in [0, T_{\max}]$: Integer variable for the scheduled start time of task $i$.$e_i \in [0, T_{\max}]$: Integer variable for the scheduled end time of task $i$.$x_{i,w} \in \{0, 1\}$: Binary variable indicating if task $i$ is executed in corridor window $w$.$z_{i,g} \in \{0, 1\}$: Binary variable indicating if task $i$ is packed into shadow group $g$.$q_i \in \{0, 1\}$: Binary variable indicating whether task $i$ is completed in this plan.4.3 Constraint Formulations1. Duration & Execution Coupling$$e_i = s_i + D_i, \quad \forall i \in \mathcal{T}$$$$\sum_{w \in \mathcal{W}} x_{i,w} = q_i, \quad \forall i \in \mathcal{T}$$2. Window Confinement (Hard Constraint)$$s_i \ge \sum_{w \in \mathcal{W}} x_{i,w} \cdot W_{s}(w), \quad \forall i \in \mathcal{T}$$$$e_i \le \sum_{w \in \mathcal{W}} x_{i,w} \cdot W_{e}(w) + M(1 - q_i), \quad \forall i \in \mathcal{T}$$3. Timetable Safety Envelope (Hard Invariant)For every task $i$ assigned to section $S(i)$ and train path $t$ running on $S(i)$:$$\text{NoOverlapInterval}\Big([s_i, e_i], \, [T_s(t) - B_{\text{before}}, \, T_e(t) + B_{\text{after}}]\Big) = \text{True}$$4. Mutual Exclusivity of Non-Shareable ResourcesFor all tasks $i, j \in \mathcal{T}$ ($i \neq j$) requiring the identical physical machine or specialized crew $r \in \mathcal{R}$:$$s_i \ge e_j \quad \lor \quad s_j \ge e_i \quad (\text{implemented via CP-SAT } \texttt{AddNoOverlap})$$5. Task PrecedenceFor all dependency pairs $(i, j)$ where task $i$ must strictly precede task $j$:$$e_i + \text{handover\_time}_{i,j} \le s_j + M(1 - q_j)$$6. Shadow Block Spatial & Isolation Compatibility$$\text{If } z_{i,g} = 1 \text{ and } z_{j,g} = 1 \implies \text{Compatible}(\text{Section}_i, \text{Section}_j) \land \text{Compatible}(\text{Iso}_i, \text{Iso}_j)$$4.4 Objective Function$$\max \quad \sum_{i \in \mathcal{T}} P_i \cdot q_i + \alpha \sum_{g \in \mathcal{G}} |g| \cdot \mathbb{I}(|g| > 1) + \beta \sum_{i \in \mathcal{T}} \frac{D_i}{\text{AvailableCorridor}} - \delta \sum_{i \in \mathcal{T}} \text{RiskOverrun}(i) \cdot q_i - \zeta \cdot \text{PlanChurn}$$Where:$\alpha$: Weight for consolidating multiple departments into shadow blocks.$\beta$: Weight for maximizing corridor packing efficiency.$\delta$: Penalty multiplier for scheduling tasks with high historical overrun risk.$\zeta$: Penalty for modifying previously approved/frozen block slots.5. API Contracts (FastAPI / OpenAPI Schema Sample)POST /api/v1/optimizer/solveRequest Payload:JSON{
  "horizon": "WEEKLY",
  "division": "DELHI",
  "start_date": "2026-09-01T00:00:00Z",
  "end_date": "2026-09-07T23:59:59Z",
  "section_ids": ["NZM-FDB", "FDB-PWL"],
  "solver_timeout_seconds": 60,
  "enforce_shadow_packing": true,
  "freeze_existing_approved": true
}
Response Payload:JSON{
  "plan_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "solver_status": "OPTIMAL",
  "solve_time_ms": 1420,
  "kpis": {
    "total_tasks_scheduled": 48,
    "total_demands_evaluated": 52,
    "shadow_block_groups_created": 14,
    "separate_blocks_avoided": 18,
    "corridor_utilization_pct": 86.4,
    "timetable_conflicts": 0
  },
  "timetable_protection_certificate": {
    "certificate_id": "CERT-2026-0901-0042",
    "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "timetable_version": "WTT-NR-2026-V2",
    "verified_zero_clash": true
  }
}
6. Comprehensive Repository Directory Treerail-bdms/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py
│   │   │   │   │   ├── assets.py
│   │   │   │   │   ├── tasks.py
│   │   │   │   │   ├── corridors.py
│   │   │   │   │   ├── trains.py
│   │   │   │   │   ├── optimizer.py
│   │   │   │   │   ├── shadow_blocks.py
│   │   │   │   │   ├── certificates.py
│   │   │   │   │   └── execution.py
│   │   │   │   └── api_router.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── events.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── models/
│   │   ├── services/
│   │   │   ├── ingestion/
│   │   │   │   ├── tms_adapter.py
│   │   │   │   ├── smms_adapter.py
│   │   │   │   ├── tdms_adapter.py
│   │   │   │   ├── coa_adapter.py
│   │   │   │   └── normalizer.py
│   │   │   ├── identity/
│   │   │   │   ├── resolver.py
│   │   │   │   └── spatial_matcher.py
│   │   │   ├── analytics/
│   │   │   │   ├── priority_engine.py
│   │   │   │   ├── duration_estimator.py
│   │   │   │   └── overrun_predictor.py
│   │   │   └── optimizer/
│   │   │       ├── compatibility_graph.py
│   │   │       ├── cpsat_scheduler.py
│   │   │       ├── constraints.py
│   │   │       ├── objectives.py
│   │   │       └── certifier.py
│   │   ├── schemas/
│   │   │   ├── asset.py
│   │   │   ├── task.py
│   │   │   ├── plan.py
│   │   │   └── certificate.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   │   ├── common/
│   │   │   ├── command_center/
│   │   │   ├── gantt/
│   │   │   ├── map/
│   │   │   ├── shadow_workbench/
│   │   │   └── execution_cockpit/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── store/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── depot-pwa/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── WorkQueue.tsx
│   │   │   ├── ReadinessChecklist.tsx
│   │   │   └── CompletionCapture.tsx
│   │   ├── db/indexedDb.ts
│   │   ├── sw.ts
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml
└── README.md

---

