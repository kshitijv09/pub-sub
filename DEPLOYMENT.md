# Running the Pub-Sub API in Docker and Deploying to Render / Other Services

## Prerequisites

- Docker installed locally ([Get Docker](https://docs.docker.com/get-docker/))
- For deployment: a Render (or other) account and a container registry or connected repo

---

## 1. Build and run the container locally

### Build the image

From the project root (where `Dockerfile` and `server.py` live):

```bash
docker build -t pubsub-api .
```

### Run the container

**X-API-Key is required.** Set `API_KEY` in the environment; clients must send header `X-API-Key: <API_KEY>`.

```bash
docker run -p 8000:8000 -e API_KEY=your-secret-key pubsub-api
```

- **HTTP:** `http://localhost:8000` (send header `X-API-Key: your-secret-key`)
- **WebSocket:** `ws://localhost:8000/ws` (send header `X-API-Key: your-secret-key` on connect)
- **Health:** `GET /health` (also requires `X-API-Key`)

### Run with all env vars

```bash
docker run -p 8000:8000 \
  -e API_KEY=your-secret-key \
  -e HEARTBEAT_INTERVAL_SEC=30 \
  -e SUBSCRIBER_QUEUE_MAX_SIZE=1024 \
  -e TOPIC_RING_BUFFER_SIZE=100 \
  pubsub-api
```

### Using a .env file

Create a `.env` file with `API_KEY=...` (do not commit). Then:

```bash
docker run -p 8000:8000 --env-file .env pubsub-api
```

---

## 2. Deploy on Render

[Render](https://render.com) can run your app as a **Web Service** from a Dockerfile or from a Git repo.

### Option A: Deploy from GitHub/GitLab (recommended)

1. **Push your code** (including `Dockerfile`, `server.py`, `pubsub/`, `requirements.txt`) to GitHub or GitLab.

2. **Create a new Web Service**
   - [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
   - Connect the repo that contains this project
   - Select the repo and branch

3. **Configure the service**
   - **Name:** e.g. `pubsub-api`
   - **Environment:** **Docker** (Render will use your `Dockerfile`)
   - **Region:** Choose the one closest to your users
   - **Instance type:** Free or paid, depending on plan

4. **Port**
   - Render expects the app to listen on the port given in the `PORT` environment variable (often `10000`).
   - Two options:
     - **Use `PORT` in the app:** In the Dockerfile or start command, run uvicorn with `--port $PORT`. Render sets `PORT` automatically.
     - **Or** in Render’s dashboard set **Environment Variable** `PORT=8000` and ensure your app listens on `8000` (our Dockerfile uses 8000 by default).  
     To be safe, we can make the Dockerfile use `PORT` if set (see below).

5. **Environment variables (Render dashboard)** — **API_KEY is required.**
   - **Key** / **Value**:
     - `API_KEY` – **required**; clients must send header `X-API-Key` with this value
     - `HEARTBEAT_INTERVAL_SEC` – optional (default 30)
     - `SUBSCRIBER_QUEUE_MAX_SIZE` – optional (default 1024)
     - `TOPIC_RING_BUFFER_SIZE` – optional (default 100)

6. **Deploy**
   - Click **Create Web Service**. Render will build the image from the Dockerfile and run the container.
   - After deploy, you get a URL like `https://pubsub-api.onrender.com`.

7. **WebSocket on Render**
   - Render supports WebSockets on the same URL. Use:
     - **HTTP:** `https://<your-service-name>.onrender.com`
     - **WebSocket:** `wss://<your-service-name>.onrender.com/ws`
   - If you use a custom domain, use that same host with `https` and `wss`.

### Option B: Deploy a pre-built image (private registry)

If you build and push the image to Docker Hub or another registry:

1. **New** → **Web Service**
2. Choose **Docker** and enter the **image URL** (e.g. `your-dockerhub-user/pubsub-api:latest`)
3. Configure **Environment** and **PORT** as above (Render still sets `PORT`; your image must listen on that port).

### Making the app use Render’s `PORT`

Render sets `PORT` (e.g. `10000`). To use it, you can change the Dockerfile CMD to:

```dockerfile
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
```

Or use a small shell script that reads `$PORT`. Simpler: in Render, add an env var **PORT** and in your start command use that port (Render’s UI often lets you override the start command).

---

## 3. Deploy on other services

Same Docker image can be used on most container platforms.

### Fly.io

```bash
# Install flyctl, then from project root
fly launch
# Choose app name, region; use Dockerfile when prompted
fly secrets set API_KEY=your-secret
fly deploy
```

- **HTTP:** `https://<app-name>.fly.dev`
- **WebSocket:** `wss://<app-name>.fly.dev/ws`

### Railway

1. **New Project** → **Deploy from GitHub** (or **Dockerfile**).
2. Connect repo; Railway detects the Dockerfile and builds/runs it.
3. Add **Variables** (e.g. `API_KEY`).
4. Railway assigns a public URL; WebSockets work on the same host with `wss://`.

### Google Cloud Run

```bash
# Build and push to Artifact Registry (or GCR), then
gcloud run deploy pubsub-api --image=<your-image> --platform=managed --allow-unauthenticated
```

Set env vars in the Cloud Run service configuration. Use the provided URL; WebSockets are supported.

### AWS (ECS / App Runner)

- **ECS:** Create a task definition that uses your Docker image, set env vars, and expose the app port. Put behind ALB or use a service URL.
- **App Runner:** Connect repo or image, set env vars and port (e.g. 8000). App Runner gives a URL; use `wss://` for WebSocket on the same host.

---

## 4. Quick reference

| Item | Value |
|------|--------|
| **Default port** | 8000 |
| **Health** | `GET /health` |
| **WebSocket** | `WS /ws` (same host, `ws://` or `wss://`) |
| **Auth (required)** | Set `API_KEY` in env; clients must send header `X-API-Key` |
| **Bind** | App binds to `0.0.0.0` so it accepts connections inside the container |

---

## 5. Checklist for production

- [ ] Set `API_KEY` in env (required); clients send header `X-API-Key`.
- [ ] Use **HTTPS** and **WSS** in production (Render/Fly/Railway provide TLS).
- [ ] Tune `SUBSCRIBER_QUEUE_MAX_SIZE` and `TOPIC_RING_BUFFER_SIZE` if needed.
- [ ] Monitor `/health` and `/stats` (e.g. from a load balancer or monitoring service).
- [ ] Remember: in-memory state (topics, queues, ring buffers) is lost on restart; for persistence you’d add a backing store (not covered here).
