# Product Requirements Document (PRD)
## Rail-BDMS: Integrated Rolling Block Demand Management System

### 1. Document Overview
* **Product Name**: Rail-BDMS (Block Demand Management System)
* **Target Environment**: Indian Railways (Divisional Control Offices, Zonal HQ, Field Depots)
* **Core Function**: Human-Supervised Multi-Department Maintenance Optimization & Corridor De-confliction Platform
* **Operational Paradigm**: Decision-Support System (DSS) with zero direct actuator/interlocking writes. Generates timetable-safe proposals for Chief Track Planning Controllers (CTPC) and Senior Divisional Operations Managers (Sr. DOM).

---

### 2. Problem Statement & Operational Context
Maintenance of railway fixed infrastructure across Indian Railways is fragmented across three distinct departmental systems:
1. **TMS (Track Management System)**: Civil/Engineering track renewal, tamping, deep screening, rail defect rectification.
2. **SMMS (Signalling Maintenance Management System)**: S&T point machines, signal replacement, axle counters, track circuit overhaul.
3. **TDMS (Traction Distribution Management System)**: Electrical/TRD Overhead Equipment (OHE) inspection, cantilever adjustments, power isolation.

Each department independently requests maintenance blocks from the Divisional Control Office. Planners manually consult the Working Time Table (WTT) and Control Office Application (COA) to reconcile conflicts. 

#### Core Operational Bottlenecks
* **Corridor Wastage**: Separate 120-minute possessions are granted on the same section across consecutive days for individual departments instead of packing them into a single multi-department possession ("Shadow Block").
* **Identity Disconnect**: TMS tracks assets by chainage (e.g., `km 124/2-124/8`), SMMS tracks by asset ID (e.g., `Point-102B`), and TDMS tracks by mast number (e.g., `Mast 124/14`).
* **Heuristic Bias**: Block granting currently relies on the loudest demand rather than quantified safety criticality, risk escalation curves, or asset degradation rates.
* **Timetable Risk**: Manual validation fails to account for non-linear goods train path propagation, headways, and adjacent section recovery buffers.

---

### 3. User Personas & Key Workflows
+-----------------------------------------------------------------------------------+
|                                FIELD LEVEL (DEPOT)                                |
|   +-----------------------+   +----------------------+   +--------------------+   |
|   |   SSE (Permanent Way) |   |    SSE (Signalling)  |   |      SSE (TRD)     |   |
|   +-----------+-----------+   +----------+-----------+   +----------+---------+   |
+---------------|--------------------------|--------------------------|-------------+
| (TMS)                    | (SMMS)                   | (TDMS)

+--------------------------+--------------------------+

|

v

+-----------------------------------------------------------------------------------+
|                       CANONICAL BDMS INGESTION & PIPELINE                         |
|  +--------------------+   +----------------------+   +-------------------------+  |
|  | Ingestion Adapters |-->| Identity Resolution  |-->| Compatibility & Packing |  |
|  +--------------------+   +----------------------+   +-------------------------+  |
+------------------------------------------|----------------------------------------+
v

+-----------------------------------------------------------------------------------+
|                     OPTIMIZATION & SAFETY VALIDATION ENGINE                       |
|  +--------------------+   +----------------------+   +-------------------------+  |
|  | CP-SAT Optimizer   |-->| Timetable Certifier  |-->| Explainable Scoring     |  |
|  +--------------------+   +----------------------+   +-------------------------+  |
+------------------------------------------|----------------------------------------+
v

+-----------------------------------------------------------------------------------+
|                           CONTROL OFFICE (DIVISIONAL HQ)                          |
|   +---------------------------------------------------------------------------+   |
|   |        Chief Track Planning Controller (CTPC) / Sr. DOM Workbench         |   |
|   |             [Review Plan] ---> [Run What-If] ---> [Formal Grant]          |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
#### 3.1 Personas
* **Chief Track Planning Controller (CTPC)**: Responsible for 26-week strategic corridors and weekly rolling block plan consolidation. Requires an explainable composite view of all cross-departmental demands.
* **Senior Divisional Operations Manager (Sr. DOM)**: Authorizing authority for corridor possessions. Focuses on punctuality, section throughput, and goods train transit targets.
* **Section Controller (Live Execution)**: Manages real-time block imposition, monitoring actual progress vs. grant window, and managing emergency restoration.
* **Depot In-Charge (Senior Section Engineer - SSE)**: Submits task requirements, confirms resource readiness (tamping machines, tower wagons, crews), and certifies physical restoration.

---

### 4. Functional Requirements

#### FR-1: Multi-System Data Ingestion & Canonicalization
* **FR-1.1**: The system shall ingest work orders, defects, and asset maintenance demands from TMS, SMMS, and TDMS via REST APIs, SFTP batch sync, and fallback structured Excel formats.
* **FR-1.2**: Ingest train movements, timetables, and dynamic freight paths from COA.
* **FR-1.3**: Map all inbound records to a single normalized canonical schema (`MaintenanceTask`, `Asset`, `CorridorWindow`, `TrainMovement`).

#### FR-2: Deterministic Asset Identity Resolution
* **FR-2.1**: Implement a tiered matching hierarchy to link disparate asset references:
  1. *Tier 1*: Exact enterprise asset identifier cross-reference match.
  2. *Tier 2*: Section ID + Line/Road + Station-From/Station-To.
  3. *Tier 3*: Chainage overlap ($[\text{km}_{\text{start}}, \text{km}_{\text{end}}]$) $\ge 90\%$.
  4. *Tier 4*: PostGIS spatial buffer proximity ($\le 25\text{ meters}$).
* **FR-2.2**: Assign a confidence score ($0.0 - 1.0$) to each match. Matches with confidence $< 0.85$ must route to a manual human reconciliation queue.

#### FR-3: Explainable Multi-Factor Priority Scoring
* **FR-3.1**: Compute a deterministic `PriorityScore` ($0-100$) for every active maintenance task:
  $$\text{PriorityScore} = 0.55 \times \text{Criticality} + 0.35 \times \text{Urgency} + 0.10 \times \text{ShadowOpportunity}$$
* **FR-3.2**: Calculate `Criticality` ($0-100$) based on track classification, speed restrictions, passenger traffic density, and asset failure consequence.
* **FR-3.3**: Calculate `Urgency` ($0-100$) based on overdue ratio ($\frac{\text{overdue days}}{\text{allowed maintenance interval}}$), defect severity class (e.g., IMR rail fractures vs routine greasing), and rate of risk escalation.
* **FR-3.4**: Expose a clear natural-language rationale explaining every score (e.g., *"Priority 88/100: Safety-critical IMR defect on High Density Network route, 12 days overdue, no redundant crossover"*).

#### FR-4: Compatible Multi-Department Shadow Block Packing
* **FR-4.1**: Build a section-level Compatibility Graph where tasks are nodes and edges denote mutual operational compatibility.
* **FR-4.2**: Verify compatibility against the following hard requirements:
  * Same Section ID and Line/Road.
  * Overlapping or adjacent spatial protection envelopes.
  * Compatible electrical isolation (e.g., TRD power block required vs track tamping permitted under power-off).
  * Signalling disconnection permit safety clearance.
* **FR-4.3**: Pack compatible tasks into a single parent `BlockGroup` (Shadow Block) with designated lead department and shared access windows.

#### FR-5: Timetable-Safe CP-SAT Constraint Optimization
* **FR-5.1**: Solve weekly and monthly block allocation schedules using Google OR-Tools CP-SAT.
* **FR-5.2 (Hard Constraints)**:
  * **Zero Train Clash**: No block window may intersect any scheduled train path plus required safety headways ($B_{\text{before}}, B_{\text{after}}$).
  * **Resource Exclusivity**: Heavy machines (e.g., BCM, CSM, Unimat, Tower Wagon) and specialized crews cannot be double-booked across concurrent blocks.
  * **Precedence Enforcement**: Dependent tasks must satisfy $e_{\text{pred}} + \text{handover\_time} \le s_{\text{succ}}$.
  * **Safety Isolation**: Tasks requiring power or signal disconnection must strictly align with certified isolation windows.
* **FR-5.3 (Objective Function)**: Maximize weighted priority task completion, maximize corridor capacity utilization, maximize shadow block consolidation, and minimize plan churn relative to baseline.

#### FR-6: Rolling Block Planning (RBP) Horizon Lifecycle
* **FR-6.1**: **26-Week Strategic Horizon**: Capacity reservation for major mega-blocks, track renewals, and bridge rebuilds.
* **FR-6.2**: **4-Week Rolling Horizon**: Detailed resource assignment, machine scheduling, and intermediate draft plan generation.
* **FR-6.3**: **1-Week Execution Horizon**: Final plan freeze by Saturday 18:00 for the subsequent week.
* **FR-6.4**: **Next-Day Finalization**: Re-validation against updated freight forecasts and live asset availability.
* **FR-6.5**: **Live Execution**: Real-time tracking of granted blocks, actual time stamps, and overrun prediction alerts.

#### FR-7: Timetable Protection Certification
* **FR-7.1**: Every generated plan must output an immutable, cryptographically verifiable `Timetable Protection Certificate` JSON object logging:
  * Zero train path conflicts.
  * Evaluated headway buffers.
  * Solver optimality status (`OPTIMAL` or `FEASIBLE`).
  * System config/policy parameter hashes.

#### FR-8: Field Execution & Closed-Loop Learning
* **FR-8.1**: Depot In-Charge PWA for offline-first check-ins, pre-work readiness checklists (crew, machine, permit, safety briefing), and actual timestamp capture.
* **FR-8.2**: Retrain duration estimation models using historical actual-versus-planned duration distributions (Quantile Regression for P50, P80, P95 metrics).

---

### 5. Non-Functional Requirements (NFRs)
* **NFR-1 (Safety Invariant)**: Under no operational condition shall the solver produce a schedule that violates a hard timetable or headway constraint.
* **NFR-2 (Solver Performance)**: Weekly division schedule optimization ($\approx 500\text{ tasks}$, $\approx 50\text{ sections}$, $\approx 1000\text{ train paths}$) must converge to an optimal or proven $\le 2\%\text{ gap}$ feasible solution within $\le 60\text{ seconds}$.
* **NFR-3 (Data Traceability)**: Every operational modification, manual priority override, and block grant action must be recorded in an append-only audit trail with user identity, timestamp, and justification.
* **NFR-4 (High Availability & Fault Tolerance)**: API availability $\ge 99.9\%$. Field PWA must support full offline queuing with IndexedDB and reconcile transparently upon reconnection.
* **NFR-5 (Enterprise RBAC)**: Strict role-based access control integrating with Railway SSO (OIDC/Keycloak).

---

### 6. Edge Cases & Mitigation Strategies

| Edge Case | Failure Mode | Mitigation Strategy |
|---|---|---|
| **Conflicting Isolation Demands** | Engineering requires diesel tamping; TRD requires OHE inspection on adjacent line with different isolation protocols. | Compatibility Engine marks the edge as incompatible. Solver allocates separate non-interfering windows or enforces sequential sub-windows. |
| **Asset Identity Ambiguity** | TMS chainage `km 104/10` maps to two different turnout IDs in SMMS due to recent yard remodeling. | Assign resolution confidence $<0.85$. Flag as `UNRESOLVED_IDENTITY`, drop from automated block group packing, and alert CTPC for one-click manual resolution. |
| **Mid-Block Machine Breakdown** | Track tamping machine fails inside the corridor at $t = +45\text{ min}$ of a 120-min block. | Execution Cockpit predicts 99% overrun risk. Triggers automated escalation alert to CTPC/Sr. DOM with emergency line-clear contingency protocols. |
| **Late Freight Path Insertion** | High-priority container train path injected into COA within the 24-hour freeze window. | Solver re-runs in `Incremental Mode`: freezes all active and approved high-priority blocks, evaluating only low-priority/uncommitted blocks for adjustment. |
| **Sudden Weather/Speed Restriction** | Heavy rainfall introduces an emergency 30 km/h speed restriction, shifting train running times and clearance windows. | Corridor Window recalculation engine automatically invalidates overlapping pre-approved windows and alerts the Section Controller. |