# Enterprise AI Agent

A production-oriented AI agent built with **FastAPI**, **Ollama**, and structured tool execution.

The agent evaluates each user request, determines whether a tool is required, executes the selected tool, and uses an LLM to generate the final response. Planning, execution, and generation are separated to improve reliability, maintainability, and testability.

The project focuses on a simple but robust agent architecture with:

* Tool-aware planning
* Structured tool execution
* Automatic recovery and replanning
* JSON Schema argument validation
* Retry and timeout protection
* Health and readiness monitoring
* Production-oriented Docker runtime

---

# Architecture

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

The architecture separates three core responsibilities:

```text
Planner
   ↓
Decide what to do

Executor
   ↓
Run the selected tool safely

Generator
   ↓
Produce the final response
```

This separation also makes individual components easier to test and replace.

---

# What This Project Demonstrates

The project is designed as a focused implementation of an LLM agent runtime rather than a collection of unrelated features.

It demonstrates how to build an agent that can:

* Decide when tool usage is necessary
* Select a registered tool
* Validate tool arguments before execution
* Execute tools with timeout and retry protection
* Recover from tool failures
* Replan when an execution attempt fails
* Generate a final user-facing response from the tool result
* Expose the entire workflow through a REST API

---

# Example Agent Flows

## Direct LLM Response

For a request that does not require a tool:

```text
User
 ↓
Planner
 ↓
No tool required
 ↓
Generator
 ↓
Answer
```

## Calculator Tool

For a mathematical request:

```text
User
 ↓
Planner
 ↓
Calculator
 ↓
Executor
 ↓
Generator
 ↓
Answer
```

Example:

```text
"What is 10 * 5?"
```

The planner selects the calculator and produces a structured tool call:

```json
{
  "tool": "calculator",
  "arguments": {
    "expression": "10 * 5"
  }
}
```

## Failure Recovery

When a tool execution fails:

```text
User
 ↓
Planner
 ↓
Executor
 ↓
Tool Failure
 ↓
Replan
 ↓
Executor
 ↓
Generator
 ↓
Answer
```

The pipeline supports bounded replanning rather than endlessly retrying failed execution.

---

# Components

## API

* Receives HTTP requests
* Validates request payloads
* Exposes the chat endpoint
* Exposes health and readiness endpoints

## Pipeline

* Orchestrates the complete agent workflow
* Coordinates planning, execution, and generation
* Handles recovery and replanning

## Planner

* Determines whether a tool is required
* Selects the appropriate tool
* Produces structured tool arguments

## Executor

* Executes tools
* Applies retries and timeouts
* Isolates tool execution failures

## Generator

* Interacts with Ollama
* Generates user-facing responses
* Applies retry and backoff policies

## Tool Registry

* Maintains the available tools
* Provides tool discovery for planning and execution

## Tool Validator

* Validates tool arguments
* Applies JSON Schema constraints before execution

---

# Features

## Agent Capabilities

* Tool-aware planning
* Structured tool calls
* Tool execution
* Automatic replanning after failures
* JSON Schema tool argument validation

## Reliability

* LLM retry and backoff
* Tool retry support
* Tool execution timeout protection
* Exception isolation
* Recovery and replanning flow

## Security

* Request validation
* Tool argument validation
* Controlled tool execution
* Safe error handling
* Non-root API container

## Runtime

* API health endpoint
* API readiness endpoint
* Docker healthchecks
* Automatic container restart policy
* Production and development dependency separation

## Testing

* Unit tests
* API tests
* Configuration tests
* Planner tests
* Generator tests
* Executor tests
* Pipeline tests
* Tool registry tests
* Tool validation tests
* Individual tool tests

---

# Available Tools

The current implementation intentionally keeps the tool set small and focused.

## Calculator

Evaluates mathematical expressions through a restricted expression evaluator.

Example:

```json
{
  "tool": "calculator",
  "arguments": {
    "expression": "10 * 5"
  }
}
```

## DateTime

Returns the current UTC date and time.

Example:

```json
{
  "tool": "datetime",
  "arguments": {}
}
```

The tool registry is designed so that additional tools can be added without changing the core planner and executor architecture.

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
  "error": null
}
```

The response exposes the selected tool and tool result so the execution flow is observable through the API.

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
* Tool execution timeout protection
* Recovery and replanning flow

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
        Run Tests
          ↓
   Build Docker Image
          ↓
      Build & Push
        to GHCR
```

The Docker image is published to GitHub Container Registry after the test job succeeds on the configured main-branch and version-tag pushes.

---

# Testing

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
* Calculator
* DateTime tool

Tests should be executed in the development environment.

Example:

```powershell
pytest -q
```

Production Docker images intentionally exclude development and test dependencies.

---

# Project Structure

```text
enterprise-ai-agent/
│
├── app/
│   ├── api.py              FastAPI endpoints
│   ├── config.py           Configuration and validation
│   ├── executor.py         Tool execution logic
│   ├── generator.py        Ollama integration
│   ├── models.py           Shared models
│   ├── pipeline.py         Agent orchestration
│   ├── planner.py          Tool planning
│   ├── tool_registry.py    Tool registration
│   └── tool_validator.py   Tool argument validation
│
├── tools/
│   ├── base.py             Tool interface
│   ├── calculator.py       Calculator tool
│   └── datetime_tool.py    Date and time tool
│
├── tests/
│   ├── test_api.py
│   ├── test_calculator.py
│   ├── test_config.py
│   ├── test_datetime_tool.py
│   ├── test_executor.py
│   ├── test_generator.py
│   ├── test_models.py
│   ├── test_pipeline.py
│   ├── test_planner.py
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

The architecture is designed so these capabilities can be introduced as additional tools or services without changing the core planner/executor flow.

---

# Future Improvements

Possible next steps include:

* Document search as an agent tool
* Agentic RAG workflows
* Additional external API tools
* Authentication and authorization
* Conversation memory
* Streaming responses
* Tracing and observability
* Evaluation and benchmark integration

---

# License

This project is licensed under the MIT License. See the `LICENSE` file for details.
