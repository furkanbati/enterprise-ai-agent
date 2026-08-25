# Enterprise AI Agent

## Overview

Enterprise AI Agent is a production-oriented AI agent built with FastAPI, Ollama, and tool execution capabilities.

The agent evaluates each user request, determines whether a tool is required, executes the tool when necessary, and uses a language model to generate the final response. The architecture separates planning, execution, and generation responsibilities to improve reliability, maintainability, and testability.

The project focuses on building a simple but robust agent architecture with:

* Tool-aware planning
* Tool execution and recovery
* Structured validation
* Retry and timeout protection
* Health and readiness monitoring
* Production-ready Docker runtime

---

## Architecture

```text
User
 ↓
FastAPI
 ↓
Pipeline
 ↓
Planner
 ↓
Tool Required?
 ├── No → Generator → Answer
 │
 └── Yes
       ↓
    Executor
       ↓
    Success?
     ├── Yes → Generator → Answer
     │
     └── No → Replan → Executor
```

### Components

#### API

* Receives HTTP requests
* Validates request payloads
* Exposes health and readiness endpoints

#### Pipeline

* Orchestrates the complete agent workflow
* Coordinates planning, execution, and generation
* Handles recovery and replanning

#### Planner

* Determines whether a tool is required
* Selects the appropriate tool
* Produces validated tool arguments

#### Executor

* Executes tools
* Applies retries and timeouts
* Isolates execution failures

#### Generator

* Interacts with Ollama
* Generates user-facing responses
* Applies retry and backoff policies

#### Tool Registry

* Maintains available tools
* Provides tool discovery for planning and execution

---

## Features

### Agent Capabilities

* Tool-aware planning
* Structured tool calls
* Tool execution
* Automatic replanning after failures
* JSON Schema tool argument validation

### Reliability

* LLM retry and backoff
* Tool retry support
* Tool execution timeout protection
* Exception isolation
* Recovery and replanning flow

### Production Readiness

* Health endpoint
* Readiness endpoint
* Configuration validation
* Docker healthchecks
* Non-root container execution
* Automatic restart policy
* Production dependency separation

### Security

* Request validation
* Tool argument validation
* Controlled tool execution
* Safe error handling

### Testing

* Unit tests
* API tests
* Configuration tests
* Planner tests
* Generator tests
* Executor tests
* Pipeline tests
* Tool validation tests

---

## Requirements

* Docker Desktop
* Docker Compose

---

## Quick Start

Build and start the containers:

```powershell
docker compose up -d --build
```

Download the model inside the Ollama container:

```powershell
docker compose exec ollama ollama pull llama3
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

## Health and Readiness

### Health Endpoint

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

### Readiness Endpoint

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

## Chat API

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
  "error": null
}
```

### Request Validation

The `question` field:

* Cannot be blank
* Cannot contain only whitespace
* Maximum length: 4000 characters

Invalid requests return:

```text
422 Unprocessable Entity
```

---

## Available Tools

### Calculator

Evaluates mathematical expressions.

Example tool call:

```json
{
  "tool": "calculator",
  "arguments": {
    "expression": "10 * 5"
  }
}
```

### DateTime

Returns the current UTC date and time.

Example tool call:

```json
{
  "tool": "datetime",
  "arguments": {}
}
```

---

## Configuration

The application is configured through environment variables.

| Variable              | Default                | Description                       |
| --------------------- | ---------------------- | --------------------------------- |
| OLLAMA_HOST           | http://localhost:11434 | Ollama server URL                 |
| CHAT_MODEL            | llama3                 | Model used for generation         |
| GENERATOR_MAX_RETRIES | 3                      | Maximum LLM retry attempts        |
| EXECUTOR_MAX_RETRIES  | 2                      | Maximum tool retry attempts       |
| PIPELINE_MAX_REPLANS  | 2                      | Maximum replanning attempts       |
| RETRY_BASE_DELAY      | 1.0                    | Initial retry delay in seconds    |
| TOOL_TIMEOUT          | 5.0                    | Tool execution timeout in seconds |

Example:

```yaml
environment:
  CHAT_MODEL: llama3
  GENERATOR_MAX_RETRIES: 5
  EXECUTOR_MAX_RETRIES: 3
  PIPELINE_MAX_REPLANS: 2
```

After changing configuration:

```powershell
docker compose up -d --build
```

---

## Production Runtime

The Docker runtime includes several production-oriented safeguards.

### Container Security

* API container runs as a non-root user
* Minimal Python base image
* Isolated application user

### Health Monitoring

* API container healthcheck
* Ollama container healthcheck
* Readiness endpoint
* Service dependency health validation

### Reliability

* Automatic container restart policy
* Retry and backoff support
* Tool execution timeout protection
* Recovery and replanning flow

### Dependency Management

* Production dependencies separated from development dependencies
* Test packages excluded from production images
* Smaller production runtime footprint

---

## Testing

The project includes tests for:

* API endpoints
* Configuration validation
* Models
* Planner
* Generator
* Executor
* Pipeline
* Tool Registry
* Tool Validator
* Individual tools

Production Docker images intentionally exclude test dependencies such as `pytest` and `pytest-cov`.

Tests should be executed in a development environment.

---

## Project Structure

```text
app/
  api.py              FastAPI endpoints
  config.py           Configuration and validation
  executor.py         Tool execution logic
  generator.py        Ollama integration
  models.py           Shared models
  pipeline.py         Agent orchestration
  planner.py          Tool planning
  tool_registry.py    Tool registration
  tool_validator.py   Tool argument validation

tools/
  base.py             Tool interface
  calculator.py       Calculator tool
  datetime_tool.py    Date and time tool

tests/
  test_api.py
  test_calculator.py
  test_config.py
  test_datetime_tool.py
  test_executor.py
  test_generator.py
  test_models.py
  test_pipeline.py
  test_planner.py
  test_tool_registry.py
  test_tool_validator.py
```

---

## Stop the Application

Stop all containers:

```powershell
docker compose down
```

Remove containers and Ollama models:

```powershell
docker compose down -v
```

This also removes downloaded Ollama models stored in the Docker volume.
