# Architecture

## Overview

Enterprise AI Agent answers questions with a native tool calling loop. The model is given the schemas of the registered tools; on each turn it either requests tool calls or gives the final answer. Tool results and errors are added to the conversation, so the model can chain tools and correct its own mistakes.

The loop itself is small. Most of the design is in the boundaries around it: what the model is allowed to do, how tool calls are validated and limited, and which rules are enforced in code rather than left to the prompt.

---

## High-Level Architecture

```text
User question
     ↓
  FastAPI  (/chat, request validation, request ID)
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

---

## Request Lifecycle

### 1. API Layer

The API receives a question through `/chat`:

```json
{
  "question": "What is 15% of 2480?"
}
```

The question is validated (non-blank, at most 4,000 characters) before it reaches the agent. Every request gets an ID that appears in logs and in the `X-Request-ID` response header.

### 2. Agent Loop

The agent starts a conversation with a system prompt and the user question, then repeats:

1. Send the conversation and the tool schemas to the model.
2. If the model returns no tool calls, its content is the final answer.
3. Otherwise, run each requested tool call through the Executor and append the result or error as a `tool` message.

A request in which the model corrects its own call, recorded with `qwen2.5:7b`:

```text
system:    rules for tool use
user:      What is 2^10? Write the expression exactly as 2^10.
assistant: tool call → calculator {"expression": "2^10"}
tool:      Error: Unsupported expression ...
assistant: tool call → calculator {"expression": "2**10"}
tool:      1024
assistant: The result of 2^10 is 1024.
```

Chaining works the same way: a later call can use an earlier result because it is already in the conversation. How reliably the model chains depends on the model; see Known Limitations in the README.

### 3. Response

The response contains the answer and a `steps` list with every tool call: tool, arguments, success, result and error. The `tool`, `arguments`, `tool_result` and `error` fields describe the last tool call, for clients written for single-tool answers.

---

## Error Handling in the Loop

Tool failures are returned to the model rather than raised:

| Failure | Message to the model | Tools stay available? |
|---|---|---|
| Malformed arguments, unsupported expression, unknown tool | `Error: ...` | Yes, the model may correct the call |
| Request rejected by the tool (`ToolRequestRejected`) | `The tool rejected this request: ...` | No, the model must explain |
| Tool call beyond the step limit | `Not executed: the tool call limit was reached.` | No |

Self-correction example:

```text
calculator {"expression": "2^10"}  → Error: Unsupported expression ...
calculator {"expression": "2**10"} → 1024
```

Failures of the model itself (connection errors, timeouts, invalid responses) are retried by the Generator and, if they persist, returned by the API as `503` or `502`.

---

## Safeguards

These rules are enforced in code, not only in the system prompt:

### Step Limit

`AGENT_MAX_STEPS` (default 5) caps the number of tool calls per request. When it is reached, the agent withdraws the tools and asks the model to answer from the results it has.

### Rejected Requests

A tool raises `ToolRequestRejected` when it understands a request but will not carry it out, for example a calculation whose result exceeds the size limit. The agent then withdraws the tools, so the only thing the model can do is explain.

This rule exists because of an observed failure: with `llama3`, after the calculator rejected `2 ** 5000000`, the model rewrote the expression as `2 ** 10` and answered `1024`. A prompt instruction not to change the user's values was not enough.

### Termination

Tool calls requested after the tools are withdrawn are not executed, and the agent returns the model's content (or a fallback answer). While tools are available, every turn executes at least one tool call, so a request finishes within `AGENT_MAX_STEPS + 2` model calls.

### Bounded Tool Output

Tool results and errors passed back to the model are limited to 4,000 characters, and integers too large for `str()` are replaced by a placeholder. The API response still contains the full result.

---

## Components

### Generator

Communicates with Ollama.

* `chat(messages, tools)` sends a conversation with tool schemas and returns a `ChatMessage` with content and tool calls
* Tool calls are normalised; JSON-string arguments are decoded, and calls without a name or with non-object arguments are rejected
* Applies `GENERATOR_TIMEOUT`, retries connection errors, timeouts and 5xx responses with exponential backoff

### Executor

Runs one tool call.

* Looks up the tool in the registry
* Validates the arguments against the tool's JSON Schema
* Runs the tool in a worker thread with `TOOL_TIMEOUT`
* Retries `ConnectionError` with backoff; timeouts are not retried
* Returns a structured `ToolResult` instead of raising

### Tool Registry

Holds the registered tools, rejects duplicate names, looks tools up by name, and exposes their schemas in the native tool calling format.

### Tool Validation

Arguments are validated against each tool's JSON Schema before execution. Tool schemas use `additionalProperties: false`, so unexpected arguments are rejected.

---

## Configuration

Application behavior is controlled through environment variables:

```text
OLLAMA_HOST
CHAT_MODEL

AGENT_MAX_STEPS
GENERATOR_MAX_RETRIES
EXECUTOR_MAX_RETRIES

RETRY_BASE_DELAY
TOOL_TIMEOUT
GENERATOR_TIMEOUT
```

Configuration is validated during startup. Invalid values prevent the application from starting.

`CHAT_MODEL` must support tool calling in Ollama. The default is `qwen2.5:7b`; `llama3` does not support tools.

---

## Reliability Features

### Retry and Backoff

The Generator retries temporary LLM failures using configurable retry limits and delays.

### Tool Retries

The Executor retries tool calls that fail with a `ConnectionError`, using exponential backoff.

Timeouts are not retried. A tool runs in a worker thread, and a thread cannot be stopped once it has started, so a timed-out call keeps running in the background. Retrying it would start a second concurrent execution of the same call and repeat any side effects.

### Timeout Protection

When a tool exceeds `TOOL_TIMEOUT`, the request stops waiting for it and receives a failed tool result.

The timeout cannot interrupt CPU-bound work that holds the Python GIL, and it does not stop the worker thread. Tools therefore bound their own work: the calculator rejects operations whose result would exceed 1,000 digits before computing them.

### Exception Isolation

Tool failures are converted into structured results. Unexpected errors in the API return a JSON `500` with the request ID and are counted in the HTTP metrics.

---

## Observability

* Logs include the request ID
* `agent_http_requests_total` and `agent_http_request_duration_seconds`, labelled by route template
* `agent_tool_calls_total` and `agent_tool_failures_total`, per tool
* `agent_tool_calls_per_request` and `agent_step_limit_reached_total` for the agent loop
* `agent_generation_total` for model calls

---

## Health Monitoring

### Health

```text
/health
```

Verifies that the API process is alive.

### Ready

```text
/ready
```

Verifies that Ollama is reachable and the configured model is available.

---

## Current Tools

### Calculator

Evaluates arithmetic expressions with a restricted evaluator: numbers, `+ - * / // % **`, parentheses, `abs`, `round`, `min`, `max`, `int`, `float`, `sqrt`, `pi` and `e`. Integer results above 1,000 digits are rejected with `ToolRequestRejected`.

### DateTime

Returns the current UTC date and time.

---

## Design Principles

### Code-Enforced Boundaries

The model decides what to do; code decides what it is allowed to do. Limits, tool withdrawal and termination do not depend on the model following instructions.

### Explicit Error Handling

Failures are represented as structured results and fed back to the model rather than raised.

### Testability

The agent is tested with a scripted model and the real Executor and tools, so the loop's behavior is verified without a running LLM.

### Production-Oriented Simplicity

The architecture avoids unnecessary abstraction while maintaining reliability and extensibility.
