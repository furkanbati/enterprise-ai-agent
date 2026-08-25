# Architecture

## Overview

Enterprise AI Agent is built around a pipeline-based architecture that separates planning, execution, and response generation into independent components.

The goal of this design is to keep responsibilities clear, improve reliability, and make the system easier to test and extend.

The Pipeline acts as the orchestration layer and coordinates all other components.

---

## High-Level Architecture

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
     └── No
           ↓
        Replan
           ↓
        Executor
```

---

## Request Lifecycle

Every request follows the same high-level flow.

### 1. API Layer

The API receives a user question through the `/chat` endpoint.

Example:

```json
{
  "question": "What is 10 * 5?"
}
```

The request is validated before entering the agent workflow.

---

### 2. Pipeline

The Pipeline is the central coordinator of the system.

Responsibilities:

* Receive the user question
* Invoke the Planner
* Execute tools when required
* Trigger replanning when necessary
* Generate the final answer

The Pipeline does not perform planning, execution, or generation itself. It only coordinates these components.

---

### 3. Planner

The Planner determines whether a tool is required.

Possible outcomes:

#### No Tool Required

```text
Question
 ↓
Planner
 ↓
No Tool
 ↓
Generator
```

Example:

```text
Who is Alan Turing?
```

The Planner may decide that a direct LLM response is sufficient.

---

#### Tool Required

```text
Question
 ↓
Planner
 ↓
Tool Call
 ↓
Executor
```

Example:

```text
What is 25 * 48?
```

The Planner generates a structured tool call.

Example:

```json
{
  "tool": "calculator",
  "arguments": {
    "expression": "25 * 48"
  }
}
```

The Planner never executes tools directly.

---

## Tool Registry

The Tool Registry maintains the list of available tools.

Responsibilities:

* Store registered tools
* Prevent duplicate registrations
* Provide tool lookup
* Expose tool metadata

The Planner uses tool metadata to understand which tools are available.

The Executor uses the registry to retrieve the selected tool.

---

## Tool Validation

Before execution, tool arguments are validated against a schema.

Example:

Valid:

```json
{
  "expression": "10 * 5"
}
```

Invalid:

```json
{
  "unknown_field": "value"
}
```

Validation prevents malformed tool calls from reaching the execution layer.

---

## Executor

The Executor is responsible for tool execution.

Responsibilities:

* Execute tools
* Apply timeout protection
* Retry recoverable failures
* Capture execution errors
* Return structured results

Successful execution:

```text
Tool
 ↓
Result
 ↓
ToolResult(success=True)
```

Failed execution:

```text
Tool
 ↓
Exception
 ↓
ToolResult(success=False)
```

The Executor isolates failures so that a single tool error cannot crash the entire request.

---

## Replanning

If tool execution fails, the system can attempt recovery.

Flow:

```text
Planner
 ↓
Tool Call
 ↓
Executor
 ↓
Failure
 ↓
Planner receives error context
 ↓
Corrected Tool Call
 ↓
Executor
```

This mechanism allows the system to recover from certain planning or argument-generation mistakes.

The maximum number of replanning attempts is controlled by:

```text
PIPELINE_MAX_REPLANS
```

---

## Generator

The Generator is responsible for communication with Ollama.

Responsibilities:

* Send prompts to the model
* Receive responses
* Retry transient failures
* Apply retry backoff

The Generator is used in two scenarios:

### Direct Response

```text
Question
 ↓
Generator
 ↓
Answer
```

### Tool-Assisted Response

```text
Question
 ↓
Planner
 ↓
Executor
 ↓
Tool Result
 ↓
Generator
 ↓
Answer
```

This allows the model to transform raw tool output into a user-friendly response.

---

## Configuration

Application behavior is controlled through environment variables.

Current configuration includes:

```text
OLLAMA_HOST
CHAT_MODEL

GENERATOR_MAX_RETRIES
EXECUTOR_MAX_RETRIES
PIPELINE_MAX_REPLANS

RETRY_BASE_DELAY
TOOL_TIMEOUT
```

Configuration is validated during startup.

Invalid values prevent the application from starting.

---

## Reliability Features

The system includes several reliability mechanisms.

### Retry and Backoff

Generator retries temporary LLM failures using configurable retry limits and delays.

### Tool Retries

Executor can retry tool execution when appropriate.

### Timeout Protection

Tool execution is limited by:

```text
TOOL_TIMEOUT
```

Long-running tools cannot block the request indefinitely.

### Exception Isolation

Failures are converted into structured results instead of propagating unhandled exceptions.

### Recovery Flow

Planner-driven replanning allows the system to recover from some tool failures.

---

## Health Monitoring

The system exposes two operational endpoints.

### Health

```text
/health
```

Used to verify that the API process is alive.

### Ready

```text
/ready
```

Used to verify that:

* Ollama is reachable
* The configured model is available

These endpoints support container health monitoring and deployment readiness checks.

---

## Current Tools

### Calculator

Purpose:

* Evaluate mathematical expressions

Example:

```text
10 * 5
```

Output:

```text
50
```

---

### DateTime

Purpose:

* Return the current UTC date and time

Example:

```text
Current UTC time
```

---

## Design Principles

### Separation of Concerns

Each component owns a single responsibility.

* Planner plans
* Executor executes
* Generator generates
* Pipeline orchestrates

### Explicit Error Handling

Failures are represented as structured results rather than uncaught exceptions.

### Testability

Components can be tested independently.

### Production-Oriented Simplicity

The architecture avoids unnecessary abstraction while maintaining reliability and extensibility.
