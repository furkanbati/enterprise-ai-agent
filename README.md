# Enterprise AI Agent

A production-oriented AI agent built with **FastAPI**, **Ollama**, and native tool calling.

The agent answers a question by running a tool calling loop: on each turn the model either calls one of the registered tools or gives the final answer. Tool results and errors are fed back into the conversation, so the agent can chain several tools and correct its own failed calls. Every tool call runs through a validated, time-limited executor, and the full trace is returned with the answer.

The project focuses on a small but robust agent runtime with:

* Native tool calling with multi-step tool chaining
* Self-correction from tool errors
* Bounded loops with code-enforced safeguards
* JSON Schema argument validation
* Timeouts, retries and resource limits
* Health, readiness and Prometheus metrics
* Production-oriented Docker runtime and CI/CD

---

# Architecture

```text
User question
     ↓
  FastAPI
     ↓
   Agent ──────────────► Generator (Ollama, with tool schemas)
     ↑                        ↓
     │                 Tool calls requested?
     │                  ├── No  → Final answer + steps
     │                  └── Yes
     │                        ↓
     │                    Executor
     │              (validate → run → timeout)
     │                        ↓
     └──── tool result or error added to the conversation
```

Responsibilities are split across small components:

| Component | Responsibility |
|---|---|
| `Agent` | Runs the tool calling loop, enforces the step limit and safeguards |
| `Generator` | Talks to Ollama; applies timeouts, retries and backoff |
| `Executor` | Validates arguments and runs a tool with a timeout |
| `ToolRegistry` | Holds the tools and exposes their schemas to the model |
| `ToolArgumentValidator` | Checks tool arguments against JSON Schema |

Each component can be tested on its own; the agent tests use a scripted model with the real executor and tools.

---

# What This Project Demonstrates

* Native tool calling through Ollama instead of hand-parsed JSON
* Multi-step reasoning: using one tool's result as input to the next
* Recovery by feeding tool errors back to the model
* Safeguards enforced in code rather than only in the prompt
* Defensive tool design: argument validation, timeouts, resource limits
* An observable agent: request IDs, Prometheus metrics, and a per-request step trace

---

# Example Agent Flows

The flows below were recorded with `qwen2.5:7b` running locally through Ollama.

## Direct Answer

```text
"Say hello in Turkish."
   → no tool calls
   → "Merhaba! How can I assist you today?"
```

## Single Tool

```text
"What is 15% of 2480?"
   → calculator {"expression": "2480 * 0.15"} → 372.0
   → "15% of 2480 is 372.0."
```

## Self-Correction

The calculator rejects `^`, and the error goes back to the model, which fixes the call:

```text
"What is 2^10? Write the expression exactly as 2^10."
   → calculator {"expression": "2^10"}  → Error: Unsupported expression ...
   → calculator {"expression": "2**10"} → 1024
   → "The result of 2^10 is 1024."
```

## Rejected Request

```text
"What is 2 to the power of 5000000?"
   → calculator {"expression": "2**5000000"} → rejected: Result exceeds 1000 digits.
   → tools withdrawn
   → the model explains that the number is too large instead of inventing a value
```

## Response Shape

```json
{
  "answer": "The result of 2^10 is 1024.",
  "tool": "calculator",
  "arguments": {"expression": "2**10"},
  "tool_result": 1024,
  "error": null,
  "steps": [
    {
      "tool": "calculator",
      "arguments": {"expression": "2^10"},
      "success": false,
      "result": null,
      "error": "Unsupported expression. Use numbers, + - * / // % **, parentheses, and abs, round, min, max, int, float, sqrt, pi or e."
    },
    {
      "tool": "calculator",
      "arguments": {"expression": "2**10"},
      "success": true,
      "result": 1024,
      "error": null
    }
  ]
}
```

`steps` lists every tool call in order. `tool`, `arguments`, `tool_result` and `error` describe the last call, so clients written for single-tool answers keep working.

---

# Safeguards

The loop is bounded, and the important rules are enforced in code:

* **Step limit.** `AGENT_MAX_STEPS` (default 5) caps tool calls per request. When it is reached, tools are withdrawn and the model is asked to answer from the results it already has.
* **Rejected requests.** When a tool raises `ToolRequestRejected`, meaning the request was understood but cannot be fulfilled, tools are withdrawn so the model can only explain the problem. Without this, a model can "succeed" by changing the user's values: in testing, `llama3` rewrote `2 ** 5000000` as `2 ** 10` and answered `1024`.
* **Termination.** Tool calls requested after tools are withdrawn are never executed, so every request finishes within `AGENT_MAX_STEPS + 2` model calls.
* **Bounded tool output.** Tool results passed back to the model are limited to 4,000 characters.
* **Tool limits.** The executor validates arguments against JSON Schema and applies `TOOL_TIMEOUT`. A thread-based timeout cannot stop CPU-bound work, so tools also bound their own work.

---

# Features

## Agent Capabilities

* Native tool calling
* Multi-step tool chaining
* Self-correction from tool errors
* Step trace in every response
* JSON Schema tool argument validation

## Reliability

* LLM request timeouts, retry and backoff
* Tool retries for connection failures
* Tool execution timeouts (timed-out calls are not retried)
* Bounded agent loop
* Exception isolation

## Security

* Request validation
* Tool argument validation
* Resource limits in tools
* Safe error handling
* Non-root API container

## Observability

* Request IDs in logs and response headers
* HTTP request metrics labelled by route
* Tool call, failure and per-request step metrics
* Health and readiness endpoints

---

# Available Tools

The current implementation intentionally keeps the tool set small and focused.

## Calculator

Evaluates mathematical expressions through a restricted expression evaluator.

Supported: numbers, `+ - * / // % **`, parentheses, `abs`, `round`, `min`, `max`, `int`, `float`, `sqrt`, `pi`, and `e`.

Integer results are limited to 1,000 digits. Oversized operations are rejected before they are computed, so a single expression cannot occupy a CPU core.

## DateTime

Returns the current UTC date and time.

New tools implement the `Tool` interface in `tools/base.py` and are added to the registry; their JSON Schema is sent to the model automatically.

---

# Requirements

* Docker Desktop
* Docker Compose

---

# Quick Start

Build and start the containers:

```powershell
docker compose up -d --build
```

Download the model inside the Ollama container:

```powershell
docker compose exec ollama ollama pull qwen2.5:7b
```

Verify that the containers are running:

```powershell
docker compose ps
```

The API will be available at:

```text
http://localhost:8000
```

---

# Health and Readiness

## Health Endpoint

Checks whether the API process is running.

```powershell
curl.exe -i http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Readiness Endpoint

Checks whether:

* Ollama is reachable
* The configured model is available

```powershell
curl.exe -i http://localhost:8000/ready
```

Expected response:

```json
{
  "status": "ready"
}
```

If Ollama is unavailable or the configured model has not been downloaded, the endpoint returns:

```text
503 Service Unavailable
```

---

# Chat API

Send a request:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"question":"What is 10 * 5?"}'
```

Example response:

```json
{
  "answer": "10 multiplied by 5 is 50.",
  "tool": "calculator",
  "arguments": {
    "expression": "10 * 5"
  },
  "tool_result": 50,
  "error": null,
  "steps": [
    {
      "tool": "calculator",
      "arguments": {"expression": "10 * 5"},
      "success": true,
      "result": 50,
      "error": null
    }
  ]
}
```

The `steps` list makes every tool call observable through the API.

---

# Request Validation

The `question` field:

* Cannot be blank
* Cannot contain only whitespace
* Has a maximum length of 4000 characters

Invalid requests return:

```text
422 Unprocessable Entity
```

Tool arguments are validated separately through JSON Schema before execution.

---

# Configuration

The application is configured through environment variables.

| Variable              | Default                | Description                       |
| --------------------- | ---------------------- | --------------------------------- |
| OLLAMA_HOST           | http://localhost:11434 | Ollama server URL                 |
| CHAT_MODEL            | qwen2.5:7b             | Model used for generation         |
| GENERATOR_MAX_RETRIES | 3                      | Maximum LLM retry attempts        |
| EXECUTOR_MAX_RETRIES  | 2                      | Maximum tool retry attempts       |
| AGENT_MAX_STEPS       | 5                      | Maximum tool calls per request    |
| RETRY_BASE_DELAY      | 1.0                    | Initial retry delay in seconds    |
| TOOL_TIMEOUT          | 5.0                    | Tool execution timeout in seconds |
| GENERATOR_TIMEOUT     | 120.0                  | LLM request timeout in seconds    |

Example:

```yaml
environment:
  CHAT_MODEL: qwen2.5:7b
  GENERATOR_MAX_RETRIES: 5
  EXECUTOR_MAX_RETRIES: 3
  AGENT_MAX_STEPS: 8
```

After changing configuration:

```powershell
docker compose up -d --build
```

---

# Production-Oriented Runtime

The Docker runtime includes several production-oriented safeguards.

## Container Security

* API container runs as a non-root user
* Minimal Python base image
* Isolated application user

## Health Monitoring

* API container healthcheck
* Ollama container healthcheck
* Readiness endpoint
* Service dependency health validation

## Reliability

* Automatic container restart policy
* Retry and backoff support
* Tool execution timeouts
* Bounded agent loop

## Dependency Management

* Production dependencies separated from development dependencies
* Test dependencies excluded from the production image
* Smaller production runtime footprint

---

# CI/CD

GitHub Actions runs the automated validation pipeline on pull requests and pushes to `main`.

The workflow:

```text
GitHub Push / Pull Request
          ↓
     Install Dependencies
          ↓
     Lint (ruff, F)
          ↓
        Run Tests
          ↓
   Build Docker Image
          ↓
      Build & Push
        to GHCR
```

The lint step runs `ruff check .` with the pyflakes rules (`F`) configured in `ruff.toml`: undefined names, unused imports and variables. It does not check style. Run on the code before the request-ID fix, it reports the undefined `get_request_id` that made every unexpected error return an empty 500.

The Docker image is published to GitHub Container Registry after the test job succeeds on the configured main-branch and version-tag pushes.

---

# Testing

The project includes tests for:

* API endpoints
* Configuration validation
* Models
* Agent loop
* Generator
* Executor
* End-to-end API flows
* Tool Registry
* Tool Validator
* Calculator
* DateTime tool

Tests should be executed in the development environment.

Example:

```powershell
ruff check .
pytest -q
```

Production Docker images intentionally exclude development and test dependencies.

---

# Project Structure

```text
enterprise-ai-agent/
│
├── app/
│   ├── agent.py            Tool calling loop
│   ├── api.py              FastAPI endpoints
│   ├── config.py           Configuration and validation
│   ├── executor.py         Tool execution logic
│   ├── generator.py        Ollama integration
│   ├── logging.py          Request ID logging
│   ├── models.py           Shared models
│   ├── tool_registry.py    Tool registration
│   └── tool_validator.py   Tool argument validation
│
├── tools/
│   ├── base.py             Tool interface
│   ├── calculator.py       Calculator tool
│   └── datetime_tool.py    Date and time tool
│
├── docs/
│   ├── architecture.md
│   └── deployment.md
│
├── tests/
│   ├── test_agent.py
│   ├── test_api.py
│   ├── test_calculator.py
│   ├── test_config.py
│   ├── test_datetime_tool.py
│   ├── test_e2e.py
│   ├── test_executor.py
│   ├── test_generator.py
│   ├── test_models.py
│   ├── test_tool_registry.py
│   └── test_tool_validator.py
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

# Current Scope

The current implementation focuses on the core agent runtime and intentionally keeps the available tools small.

It does not currently include:

* External SaaS/API tools
* Document retrieval
* Authentication and authorization
* Conversation persistence
* Web-based UI

The architecture is designed so these capabilities can be introduced as additional tools or services without changing the agent loop.

---

# Known Limitations

* **Model reasoning.** The loop supports chaining tools, and this is covered by tests, but a 7B model does not always use it. In local runs `qwen2.5:7b` tended to do date arithmetic itself after calling `datetime` instead of passing the dates to the calculator, and answered "How many days are left until New Year's Eve?" inconsistently. A larger model or a dedicated date tool would help; an evaluation suite would measure it.
* **Unverified final steps.** After a tool error, the model sometimes states the corrected result without calling the tool again. Its answers for `2^10` were correct, but the value was not computed by the tool in that run.
* **Thread-based timeouts.** A timed-out tool keeps running in its worker thread. Tools bound their own work, but full isolation would need a separate process per call.

---

# Future Improvements

Possible next steps include:

* Document search as an agent tool (Agentic RAG)
* Additional external API tools
* Authentication and authorization
* Conversation memory
* Streaming responses
* Tracing and observability
* An evaluation suite for tool selection and answer accuracy
* Process-isolated tool execution

---

# License

This project is licensed under the MIT License. See the `LICENSE` file for details.
