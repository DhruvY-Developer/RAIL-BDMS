# Rail-BDMS Deployment Guide

This guide covers all deployment options for the **Rail-BDMS** platform (Local Network, Free Cloud Hosting, Docker, and Production Cloud).

---

## Option 1: Free 1-Click Cloud Deployment (Render / Railway)

### Deploy on Render (Free)
1. Push this project folder to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Rail-BDMS"
   git remote add origin https://github.com/YOUR_USERNAME/rail-bdms.git
   git push -u origin main
   ```
2. Go to [render.com](https://render.com) and create a free account.
3. Click **"New Web Service"** $\to$ Connect your GitHub repository.
4. Fill in the deployment details:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
5. Click **"Create Web Service"**.
6. Render will automatically build the container and provide you with a live HTTPS public URL (e.g. `https://rail-bdms.onrender.com`).

---

### Deploy on Railway (Free / One-Click)
1. Go to [railway.app](https://railway.app).
2. Click **"New Project"** $\to$ **"Deploy from GitHub Repo"**.
3. Select your repository. Railway automatically detects `requirements.txt` and `Procfile` and deploys the application with a public domain.

---

## Option 2: Docker Container Deployment

### 1. Build and Run with Docker
```bash
# Build the Docker image
docker build -t rail-bdms:latest .

# Run the container
docker run -d -p 8000:8000 --name rail_bdms rail-bdms:latest
```

### 2. Run with Docker Compose
```bash
docker-compose up -d
```
Access the application at: `http://localhost:8000`

---

## Option 3: Local / Institutional Network Deployment

To share the application with other devices on your local Wi-Fi / LAN (e.g. tablet for Field SSE Cockpit, other laptops for CTPC / Sr. DOM):

1. Find your local machine's IP address:
   - On Windows: Run `ipconfig` in CMD/PowerShell (look for **IPv4 Address**, e.g., `192.168.1.45`).
2. Run the start script:
   ```bash
   py -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
   *(Or double-click `start_server.bat`)*
3. On any mobile, tablet, or PC connected to the same network, open:
   ```text
   http://192.168.1.45:8000
   ```

---

## Option 4: Production Cloud (Google Cloud Run / AWS / Azure)

### Deploy to Google Cloud Run
```bash
# Build image using Cloud Build
gcloud builds submit --tag gcr.io/PROJECT_ID/rail-bdms

# Deploy to Cloud Run
gcloud run deploy rail-bdms \
  --image gcr.io/PROJECT_ID/rail-bdms \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8000
```

---

## Verification Endpoints
- **Web App**: `http://localhost:8000/`
- **Swagger Docs**: `http://localhost:8000/docs`
- **Health Check / KPIs**: `http://localhost:8000/api/v1/overview/kpis`
