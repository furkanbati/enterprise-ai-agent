# Deployment

## Overview

Enterprise AI Agent is deployed as two Docker Compose services:

```text
┌─────────────────────┐
│      agent-api      │
│      FastAPI        │
│      Port 8000      │
└──────────┬──────────┘
           │
           │ HTTP
           ↓
┌─────────────────────┐
│       ollama        │
│      LLM Runtime    │
│      Port 11434     │
└─────────────────────┘
```

The API container communicates with Ollama through the Docker Compose network.

The API uses:

```text
OLLAMA_HOST=http://ollama:11434
```

---

## Requirements

The deployment requires:

* Docker Desktop
* Docker Compose

The application does not require a separate Python installation when running through Docker.

---

## Start the Application

Build the API image and start all services:

```powershell
docker compose up -d --build
```

Check the service status:

```powershell
docker compose ps
```

Both services should eventually report a healthy state where healthchecks are configured.

---

## Services

### agent-api

The `agent-api` service:

* Builds from the project Dockerfile
* Exposes port `8000`
* Runs the FastAPI application with Uvicorn
* Uses a non-root application user
* Includes an API healthcheck
* Restarts automatically when configured by Docker

The API is available at:

```text
http://localhost:8000
```

---

### ollama

The `ollama` service:

* Uses the official Ollama container image
* Stores downloaded models in a persistent Docker volume
* Provides the LLM runtime for the API
* Includes a healthcheck
* Restarts automatically when configured by Docker

The Ollama service is not published directly to the host.

The API communicates with it internally through:

```text
http://ollama:11434
```

---

## Service Dependency

The API depends on Ollama being healthy before startup continues.

Docker Compose uses:

```yaml
depends_on:
  ollama:
    condition: service_healthy
```

This prevents the API from starting against an unavailable Ollama service during normal startup.

This is a startup dependency check, not a guarantee that Ollama will remain healthy for the entire lifetime of the application.

Runtime failures are handled separately by the application's readiness checks and error handling.

---

## Healthchecks

### API Healthcheck

The API Docker image defines a healthcheck that requests:

```text
http://127.0.0.1:8000/health
```

The endpoint confirms that the API process is responding.

### Ollama Healthcheck

The Ollama container uses:

```text
ollama list
```

as its healthcheck command.

This verifies that the Ollama runtime is available inside the container.

---

## Health and Readiness

The application exposes two different operational endpoints.

### `/health`

Checks API liveness:

```powershell
curl.exe -i http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

### `/ready`

Checks application readiness:

```powershell
curl.exe -i http://localhost:8000/ready
```

The readiness check verifies that Ollama and the configured model are available.

If the required dependency is unavailable, the endpoint returns:

```text
503 Service Unavailable
```

This distinction allows liveness and dependency readiness to be treated separately.

---

## Ollama Model Setup

The default model is:

```text
llama3
```

After starting the containers, download the model into the Ollama container:

```powershell
docker compose exec ollama ollama pull llama3
```

Verify the installed model:

```powershell
docker compose exec ollama ollama list
```

Once the model is available, check application readiness:

```powershell
curl.exe -i http://localhost:8000/ready
```

---

## Persistent Model Storage

Downloaded Ollama models are stored in the Docker volume:

```text
ollama_data
```

The volume is mounted to:

```text
/root/.ollama
```

This means downloaded models survive normal container recreation.

For example:

```powershell
docker compose down
```

does not remove the model volume.

---

## Removing Models

To remove containers and the Ollama volume:

```powershell
docker compose down -v
```

This also removes downloaded Ollama models.

The models will need to be downloaded again after the next deployment.

---

## Restart Policy

Both services use:

```yaml
restart: unless-stopped
```

This allows Docker to automatically restart containers after failures or Docker daemon restarts, unless the services have been explicitly stopped.

---

## Container Security

The API Docker image creates a dedicated application user:

```text
appuser
```

The application runs as this user rather than `root`.

This reduces the privileges available to the application process inside the container.

The Dockerfile also uses a minimal Python base image:

```text
python:3.12-slim
```

---

## Production Dependencies

Production and development dependencies are separated.

The production image installs:

```text
requirements.txt
```

Development dependencies are kept separately in:

```text
requirements-dev.txt
```

Test packages such as:

```text
pytest
pytest-cov
```

are intentionally excluded from the production image.

This keeps the production runtime smaller and avoids shipping unnecessary development tooling.

---

## Configuration

The API configuration is controlled through environment variables.

| Variable                | Default                  | Description            |
| ----------------------- | ------------------------ | ---------------------- |
| `OLLAMA_HOST`           | `http://localhost:11434` | Ollama endpoint        |
| `CHAT_MODEL`            | `llama3`                 | LLM model              |
| `GENERATOR_MAX_RETRIES` | `3`                      | LLM retry limit        |
| `EXECUTOR_MAX_RETRIES`  | `2`                      | Tool retry limit       |
| `PIPELINE_MAX_REPLANS`  | `2`                      | Replanning limit       |
| `RETRY_BASE_DELAY`      | `1.0`                    | Initial retry delay    |
| `TOOL_TIMEOUT`          | `5.0`                    | Tool execution timeout |

Inside Docker Compose, the API overrides the Ollama endpoint with:

```yaml
OLLAMA_HOST: http://ollama:11434
```

because `ollama` is the Docker Compose service name.

---

## Image Pinning

The Ollama image is referenced using a SHA-256 digest rather than an unpinned mutable tag.

This makes the deployed Ollama image deterministic and reduces the risk of an unexpected image change during deployment.

The API image is built locally from the project's `Dockerfile`.

---

## Docker Build

The API image:

1. Uses Python 3.12 slim
2. Sets `/app` as the working directory
3. Installs production dependencies
4. Copies the application source
5. Creates a dedicated non-root user
6. Changes ownership of the application directory
7. Runs the application as the non-root user
8. Defines a healthcheck
9. Starts Uvicorn

Build manually if required:

```powershell
docker compose build agent-api
```

Start the API:

```powershell
docker compose up -d agent-api
```

---

## Deployment Verification

After deployment, verify the containers:

```powershell
docker compose ps
```

Verify API liveness:

```powershell
curl.exe -i http://localhost:8000/health
```

Verify application readiness:

```powershell
curl.exe -i http://localhost:8000/ready
```

Verify the chat endpoint:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"question":"What is 10 * 5?"}'
```

A successful deployment should therefore satisfy:

```text
Containers
   ↓
Healthy
   ↓
API /health
   ↓
API /ready
   ↓
Chat request
```

---

## Updating the Application

After changing application code or production dependencies, rebuild the API image:

```powershell
docker compose up -d --build agent-api
```

Then verify:

```powershell
docker compose ps
```

and:

```powershell
curl.exe -i http://localhost:8000/ready
```

---

## Stopping the Deployment

Stop the services:

```powershell
docker compose down
```

This removes the containers but preserves the Ollama volume.

To remove the volume and downloaded models as well:

```powershell
docker compose down -v
```

---

## Production Runtime Principles

The deployment configuration follows several production-oriented principles:

* Run application containers as non-root
* Keep production dependencies minimal
* Use healthchecks for service monitoring
* Separate liveness from readiness
* Wait for critical dependencies to become healthy
* Restart failed services automatically
* Persist downloaded LLM models
* Pin critical external container images
* Validate configuration at application startup
* Keep development and test dependencies out of production images

The goal is to keep the deployment simple while providing predictable and recoverable runtime behavior.
