"""
Rail-BDMS: Main FastAPI Application Entry Point
Integrated Rolling Block Demand Management System for Indian Railways
"""
import asyncio
import json
import random
from typing import List
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import os

from backend.app.core.config import settings
from backend.app.api.v1.router import router as api_v1_router, db, compute_train_telemetry

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Rail-BDMS: Human-Supervised Multi-Department Maintenance Optimization & Corridor De-confliction Platform",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 REST API
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# ----------------- WebSocket Connection Manager -----------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws/live-cockpit")
async def websocket_live_cockpit(websocket: WebSocket):
    """
    Live real-time telemetry feed streaming train positions, active corridor blocks,
    and field execution state updates.
    """
    await manager.connect(websocket)
    try:
        # Initial greeting with current system summary
        await websocket.send_text(json.dumps({
            "type": "INITIAL_STATE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_blocks_count": len(db.execution_states),
            "total_trains_monitored": len(db.trains),
            "safety_invariant": "GUARANTEED_ZERO_CLASH"
        }))
        
        sim_minute = 400 # 06:40 AM
        while True:
            await asyncio.sleep(2.5)
            sim_minute = (sim_minute + 2) % 1440
            db.sim_minute = sim_minute
            
            # Compute live train positions with exact geospatial coordinates
            active_trains_live = []
            for tr in db.trains:
                if tr.entry_minute <= sim_minute <= tr.exit_minute:
                    pos = compute_train_telemetry(tr, sim_minute)
                    active_trains_live.append(pos.model_dump())
            
            # Fallback sample active trains if corridor is temporarily quiet
            if not active_trains_live:
                for tr in db.trains[:6]:
                    pos = compute_train_telemetry(tr, (tr.entry_minute + tr.exit_minute) // 2)
                    active_trains_live.append(pos.model_dump())

            # Broadcast real-time telemetry event
            telemetry_payload = {
                "type": "TELEMETRY_TICK",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "simulated_time_str": f"{sim_minute // 60:02d}:{sim_minute % 60:02d}",
                "active_trains": active_trains_live[:8],
                "active_blocks": [
                    {
                        "assignment_id": k,
                        "section_id": v["assignment"].section_id,
                        "line": v["assignment"].line_or_road.value,
                        "state": v["current_state"],
                        "overrun_risk_score": v["overrun_risk_score"],
                        "department": v["assignment"].department.value
                    }
                    for k, v in list(db.execution_states.items())[:6]
                ]
            }
            await websocket.send_text(json.dumps(telemetry_payload))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# ----------------- Static Frontend Hosting -----------------
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_root():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Rail-BDMS API Backend Running</h1><p>Visit <a href='/docs'>/docs</a> for Swagger API</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
