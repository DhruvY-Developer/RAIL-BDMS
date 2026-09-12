# Rail-BDMS: Integrated Rolling Block Demand Management System

> **AI-Powered Human-Supervised Maintenance Optimization & Corridor De-confliction Platform for Indian Railways**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![OR-Tools](https://img.shields.io/badge/Google%20OR--Tools-CP--SAT-red.svg)](https://developers.google.com/optimization)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🚆 Overview

Maintenance of railway fixed infrastructure across Indian Railways is fragmented across three distinct departmental silos:
1. **TMS (Track Management System)**: Civil/Engineering track renewal, machine tamping, deep screening, and rail defect rectification.
2. **SMMS (Signalling Maintenance Management System)**: S&T point machines, signal replacement, axle counters, and track circuit overhauls.
3. **TDMS (Traction Distribution Management System)**: Electrical/TRD Overhead Equipment (OHE) inspection, cantilever adjustments, and power isolation.

**Rail-BDMS** acts as a next-generation **Decision-Support System (DSS)** that unifies multi-departmental maintenance demands, resolves spatial identity discrepancies across differing reference systems, eliminates corridor wastage via intelligent **"Shadow Block" packing**, and certifies conflict-free possession windows without disrupting critical train timetables.

---

## 🌟 Key Features

* **Multi-Department Ingestion & De-confliction**: Ingests maintenance demands across TMS, SMMS, and TDMS into a canonical data format.
* **Canonical Identity Resolution & GIS Mapping**: Translates departmental references (Track chainage `km 124/2-124/8`, S&T asset ID `Point-102B`, and TRD mast number `Mast 124/14`) into unified track segments and geographical coordinates.
* **Constraint Programming Scheduler (Google OR-Tools CP-SAT)**:
  * Hard conflict avoidance: Headways, safety buffers, and train paths.
  * Soft preference optimization: Prioritizing deferred work, equipment proximity, and minimal passenger delay penalties.
* **Shadow Block Bundling**: Aggregates overlapping possessions into high-efficiency coordinated multi-departmental possession windows.
* **Real-Time Live Telemetry & Simulation**: Simulates train movements and dynamically computes headway violations and corridor safety alerts via WebSockets.
* **Multi-Persona Mission Control Dashboard**:
  * **SSE Cockpit (Depot Level)**: Demand submission, machine/crew requirements, and slot feedback.
  * **CTPC View (Chief Track Planning Controller)**: Corridor packing matrix, conflict heatmaps, and Gantt charts.
  * **Sr. DOM Authorization (Senior Divisional Operations Manager)**: Timetable safety certification, train delay impact analysis, and one-click block granting.
* **Production-Ready & Containerized**: Ready for 1-click cloud deployment on Render/Railway, Docker, or Google Cloud Run.

---

## 🏛️ System Architecture

```
+-----------------------------------------------------------------------------------+
|                                FIELD LEVEL (DEPOT)                                |
|   +-----------------------+   +----------------------+   +--------------------+   |
|   |   SSE (Permanent Way) |   |    SSE (Signalling)  |   |      SSE (TRD)     |   |
|   +-----------+-----------+   +----------+-----------+   +----------+---------+   |
+---------------|--------------------------|--------------------------|-------------+
                | (TMS)                    | (SMMS)                   | (TDMS)
                v                          v                          v
+-----------------------------------------------------------------------------------+
|                       CANONICAL BDMS INGESTION & PIPELINE                         |
|  +--------------------+   +----------------------+   +-------------------------+  |
|  | Ingestion Adapters |-->| Identity Resolution  |-->| Compatibility & Packing |  |
|  +--------------------+   +----------------------+   +-------------------------+  |
+------------------------------------------|----------------------------------------+
                                           v
+-----------------------------------------------------------------------------------+
|                       CP-SAT OPTIMIZATION & SCHEDULER ENGINE                      |
|  +--------------------+   +----------------------+   +-------------------------+  |
|  | Priority Engine    |-->| Google OR-Tools CP   |-->| Conflict Certifier      |  |
|  +--------------------+   +----------------------+   +-------------------------+  |
+------------------------------------------|----------------------------------------+
                                           v
+-----------------------------------------------------------------------------------+
|                     REAL-TIME DASHBOARD & MISSION CONTROL UI                      |
|  +--------------------+   +----------------------+   +-------------------------+  |
|  | Corridor Map & GIS |   | Gantt Scheduling     |   | Live Telemetry WS       |  |
|  +--------------------+   +----------------------+   +-------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 📂 Repository Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   └── router.py                # REST API routes & WebSocket endpoints
│   │   ├── core/
│   │   │   └── config.py                # Configuration & environment settings
│   │   ├── schemas/
│   │   │   └── schemas.py               # Pydantic models & canonical schemas
│   │   ├── services/
│   │   │   ├── analytics/
│   │   │   │   └── priority_engine.py   # Demand scoring & degradation curves
│   │   │   ├── identity/
│   │   │   │   └── resolver.py          # Multi-department GIS asset resolution
│   │   │   ├── ingestion/
│   │   │   │   └── mock_data.py         # Seed corridors, demands & timetables
│   │   │   └── optimizer/
│   │   │       ├── certifier.py         # Safety & timetable compliance rules
│   │   │       ├── compatibility.py     # Co-utilization & shadow block logic
│   │   │       ├── cpsat_scheduler.py   # Google OR-Tools mathematical solver
│   │   │       └── horizon_orchestrator.py # Multi-day rolling horizon planner
│   │   └── main.py                      # FastAPI application entrypoint
│   └── tests/
│       ├── benchmark_e2e_simulation.py  # End-to-end performance benchmark
│       ├── test_all.py                  # Full test suite
│       ├── test_auth.py                 # Authorization & role tests
│       └── test_gis.py                  # Linear referencing & asset tests
├── frontend/
│   ├── app.js                           # Dashboard application logic & WS client
│   ├── index.html                       # Responsive Mission Control interface
│   └── styles.css                       # Modern dark-mode styling & layout
├── docs/
│   ├── AGENT_RULES.md                   # Operational guardrails & specifications
│   ├── ARCHITECTURE.md                  # Detailed software architecture document
│   ├── DEPLOYMENT_GUIDE.md              # Multi-environment deployment steps
│   ├── PRD.md                           # Product Requirements Document (PRD)
│   └── TASK.md                          # Engineering breakdown & implementation tasks
├── Dockerfile                           # Production multi-stage Docker build
├── docker-compose.yml                   # Container orchestration config
├── Procfile                             # Process file for Heroku / Railway
├── render.yaml                          # Infrastructure-as-code for Render
├── requirements.txt                     # Python dependencies
├── start_server.bat                     # Windows quickstart launcher
└── README.md                            # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+** installed
- **Git** installed

### 1. Local Setup
Clone the repository and install dependencies:
```bash
git clone https://github.com/DhruvY-Developer/RAIL-BDMS.git
cd RAIL-BDMS

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run the Application
Start the FastAPI server:
```bash
# Option A: Direct uvicorn
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Option B: Windows batch file
start_server.bat
```

Once running, access:
- **Interactive Web Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🐳 Docker Deployment

### Build and Run with Docker
```bash
# Build the Docker image
docker build -t rail-bdms:latest .

# Run container on port 8000
docker run -d -p 8000:8000 --name rail-bdms-app rail-bdms:latest
```

### Run with Docker Compose
```bash
docker-compose up -d
```
Access at [http://localhost:8000](http://localhost:8000).

---

## ☁️ Cloud Deployment

### Deploy on Render

#### Option A: 1-Click Blueprint (Recommended)
1. Push your repository to GitHub.
2. Go to the [Render Dashboard](https://dashboard.render.com).
3. Click **New +** $\to$ **Blueprint**.
4. Connect your repository (`RAIL-BDMS`).
5. Render detects [`render.yaml`](file:///render.yaml) automatically:
   - **Runtime**: Python 3.11.8
   - **Build Command**: `python -m pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check**: `/health`
6. Click **Apply** to launch the service.

#### Option B: Manual Web Service Setup
If creating a service manually in the Render dashboard:
- **Runtime**: `Python`
- **Build Command**: `python -m pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- **Advanced $\to$ Health Check Path**: `/health`
- **Advanced $\to$ Environment Variables**:
  - `PYTHON_VERSION` = `3.11.8`
  - `PYTHONPATH` = `.`

#### Option C: Docker on Render
- Choose **Docker** as runtime in Render; it will automatically build using [`Dockerfile`](file:///Dockerfile) and respect [`dockerignore`](file:///.dockerignore).

### Deploy on Railway
1. Sign in to [railway.app](https://railway.app).
2. Select **New Project** $\to$ **Deploy from GitHub Repo**.
3. Select `RAIL-BDMS` — deployment triggers automatically using [`Procfile`](file:///Procfile).

---

## 🧪 Testing

Execute automated unit tests and solver benchmarks:
```bash
# Run all tests
pytest backend/tests/test_all.py -v

# Run GIS linear referencing tests
pytest backend/tests/test_gis.py -v

# Run E2E simulation benchmark
python backend/tests/benchmark_e2e_simulation.py
```

---

## 📜 License

This project is developed for the Smart India Hackathon (SIH) and is open for academic and research evaluation.
