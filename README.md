# Enterprise AI Agent

A production-oriented AI agent built with **FastAPI** and native tool calling. It runs on a local model through **Ollama**, or on **OpenAI** or **Anthropic (Claude)**, selected with one environment variable.

The agent answers a question by running a tool calling loop: on each turn the model either calls one of the registered tools or gives the final answer. Tool results and errors are fed back into the conversation, so the agent can chain several tools and correct its own failed calls. Every tool call runs through a validated, time-limited executor, and the full trace is returned with the answer.

It ships with a **customer support scenario** for an online electronics store: the agent looks up customers and orders, checks shipping and return status, answers from the store's policies, and opens support tickets, on demo data in SQLite.

The project focuses on a small but robust agent runtime with:

* Native tool calling with multi-step tool chaining
* Business tools for customers, orders, policies and support tickets
* Ollama, OpenAI (and compatible APIs) or Anthropic behind one provider interface
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
   Agent ──────────────► Generator ──► Provider (Ollama | OpenAI | Anthropic)
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
| `Generator` | Calls the configured provider; applies retries and backoff |
| `ChatProvider` | Converts the conversation and tool schemas to one LLM API and back |
| `Executor` | Validates arguments and runs a tool with a timeout |
| `ToolRegistry` | Holds the tools and exposes their schemas to the model |
| `ToolArgumentValidator` | Checks tool arguments against JSON Schema |

Each component can be tested on its own; the agent tests use a scripted model with the real executor and tools.

---

# What This Project Demonstrates

* Native tool calling instead of hand-parsed JSON
* One agent loop on three LLM APIs: the provider layer converts tool calls, tool results and IDs to each API
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
      "error": "Unsupported expression. Use numbers, + - * / // % **, parentheses, and abs, round, min, max, int, float, sqrt, pi or e.",
      "rejected": false
    },
    {
      "tool": "calculator",
      "arguments": {"expression": "2**10"},
      "success": true,
      "result": 1024,
      "error": null,
      "rejected": false
    }
  ]
}
```

`steps` lists every tool call in order; `rejected` is true when a tool refused the request (see Safeguards). `tool`, `arguments`, `tool_result` and `error` describe the last call, so clients written for single-tool answers keep working.

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

# Customer Support Scenario

The support tools work on a small online electronics store: 6 customers, 8 orders and 6 policy sections, created in SQLite (`BUSINESS_DB_PATH`) on first use. The demo data includes a late delivery, a return window that has just closed, one that is still open, and orders that can still be cancelled.

| Tool | What it does |
|---|---|
| `find_customer` | Finds customers by email, name or ID. Returns several matches when a name is ambiguous, so the agent can ask which one is meant. |
| `list_customer_orders` | Lists a customer's orders, optionally by status. |
| `get_order` | Items, total, tracking, and computed facts: `delivery_late`, `days_past_estimated_delivery`, `return_window_ends`, `returnable`, `cancellable`. |
| `search_policies` | Returns the policy sections that match a question, or says that none matches. |
| `create_support_ticket` | Opens a ticket for a customer and, optionally, one of their orders. |

An example, recorded as a test with the real tools ([`test_support_tools.py`](tests/test_support_tools.py)):

```text
"Elif's headphones have not arrived. Please open a ticket."
   → find_customer {"query": "elif.yilmaz@example.com"}        → CUS-1001
   → get_order {"order_id": "ORD-5001"}                       → delivery_late: true, 9 days past the estimate
   → create_support_ticket {"customer_id": "CUS-1001", "order_id": "ORD-5001",
                            "category": "delivery", "priority": "high", ...} → TCK-1001
   → "Ticket TCK-1001 is open for ORD-5001."
```

Design decisions:

* **The tools compute what depends on today's date.** Whether an order is late or still returnable comes from the tool, not from the model. The evaluation showed the model getting date arithmetic wrong until a tool returned the answer (see the weekday and `date_diff` results below).
* **Ticket creation is idempotent.** A model can repeat a call, and a timed-out call keeps running in its thread. An open ticket for the same customer, order and category is returned (`"created": false`) instead of a duplicate. The check and the insert run in one SQLite transaction, so concurrent calls also create one ticket.
* **Arguments are validated before anything runs.** IDs must match `CUS-0000` / `ORD-0000`, categories and priorities are enums, and an order must belong to the customer on the ticket. Errors go back to the model with a hint, such as "use find_customer to look up the ID".
* **Data minimisation.** The tools return what a support conversation needs, with no addresses, phone numbers or payment details.
* **Tool results reach the model as JSON**, which models read more reliably than Python's repr.

Policy search matches keywords over six short sections. Searching real policy documents (RAG) would replace it behind the same tool.

---

# Available Tools

Besides the support tools, the agent has three general tools.

## Calculator

Evaluates mathematical expressions through a restricted expression evaluator.

Supported: numbers, `+ - * / // % **`, parentheses, `abs`, `round`, `min`, `max`, `int`, `float`, `sqrt`, `pi`, and `e`.

Integer results are limited to 1,000 digits. Oversized operations are rejected before they are computed, so a single expression cannot occupy a CPU core.

## DateDiff

Returns the number of days between two `YYYY-MM-DD` dates, negative if the end date is earlier.

```json
{"tool": "date_diff", "arguments": {"start": "2026-10-17", "end": "2026-12-25"}}
```

Result: `69`. It was added after the evaluation showed the model counting days itself and getting them wrong.

## DateTime

Returns the current UTC date and time with the day of the week:

```json
{"datetime": "2026-10-17T09:00:00+00:00", "weekday": "Saturday"}
```

The weekday is computed by the tool. When the tool returned only the timestamp, the model named the wrong weekday in every evaluation run.

New tools implement the `Tool` interface in `tools/base.py` and are added to the registry; their JSON Schema is sent to the model automatically.

---

# Requirements

* Docker Desktop
* Docker Compose

---

# Quick Start

The default provider is Ollama, which runs the model locally. To use OpenAI or Anthropic instead, copy `.env.example` to `.env` and set the provider, model and API key:

```text
LLM_PROVIDER=openai
CHAT_MODEL=<an OpenAI model with tool calling>
OPENAI_API_KEY=...
```

```text
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
```

Docker Compose reads `.env` automatically. With a cloud provider, pulling an Ollama model is not needed.

Build and start the containers:

```powershell
docker compose up -d --build
```

With Ollama, download the model inside the Ollama container:

```powershell
docker compose exec ollama ollama pull qwen2.5:7b
```

Verify that the containers are running:

```powershell
docker compose ps
```

The demo UI and the API will be available at:

```text
http://localhost:8000
```

---

# Demo UI

Opening `http://localhost:8000` shows a chat UI for the Perwatt Electronics support scenario (Perwatt is a fictional store).

* **Chat** with sample questions to start from. The conversation is multi-turn: the agent can ask which customer is meant, and the answer reaches it.
* **Agent trace** panel: every tool call of an answer, with its arguments, result, and whether it succeeded, failed or was rejected.
* **Demo data** panel: the customers and orders the agent works on. Clicking an ID inserts it into the question.
* **Reset demo** restores the demo data and removes the tickets opened since.
* The provider and model in use are shown in the header.

The UI is a single HTML file ([`app/static/index.html`](app/static/index.html)) with plain JavaScript, served by FastAPI. It needs no build step, no extra container and no dependencies. It calls the same endpoints any other client would:

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Ask a question, with the earlier turns in `history` |
| `GET /info` | Provider and model |
| `GET /demo/customers`, `GET /demo/orders` | Read-only demo data |
| `POST /demo/reset` | Restore the demo data |

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

* The configured provider is reachable
* The configured model is available (for Ollama: it has been pulled)

```powershell
curl.exe -i http://localhost:8000/ready
```

Expected response:

```json
{
  "status": "ready"
}
```

If the provider is unreachable, the API key is invalid, or the model is not available, the endpoint returns:

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

## Conversations

The API is stateless: the client keeps the conversation and sends the earlier turns in `history`, oldest first. Only user questions and assistant answers are sent; the model calls the tools again when it needs earlier results.

```json
{
  "question": "Elif Yılmaz.",
  "history": [
    {"role": "user", "content": "Show me the orders of Elif."},
    {"role": "assistant", "content": "Two customers are called Elif: Elif Yılmaz (CUS-1001) and Elif Demir (CUS-1006). Which one do you mean?"}
  ]
}
```

`history` holds at most 10 messages and 20,000 characters, each message at most 4,000 characters. Roles other than `user` and `assistant` are rejected, so a client cannot inject system or tool messages.

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
| LLM_PROVIDER          | ollama                 | `ollama`, `openai` or `anthropic` |
| CHAT_MODEL            | per provider           | Model used for generation         |
| OLLAMA_HOST           | http://localhost:11434 | Ollama server URL                 |
| OPENAI_API_KEY        |                        | Required for `openai`             |
| OPENAI_BASE_URL       | OpenAI API             | Any OpenAI-compatible API         |
| ANTHROPIC_API_KEY     |                        | Required for `anthropic`          |
| BUSINESS_DB_PATH      | var/business.db        | SQLite file for the demo data     |
| GENERATOR_MAX_RETRIES | 3                      | Maximum LLM retry attempts        |
| EXECUTOR_MAX_RETRIES  | 2                      | Maximum tool retry attempts       |
| AGENT_MAX_STEPS       | 5                      | Maximum tool calls per request    |
| RETRY_BASE_DELAY      | 1.0                    | Initial retry delay in seconds    |
| TOOL_TIMEOUT          | 5.0                    | Tool execution timeout in seconds |
| GENERATOR_TIMEOUT     | 120.0                  | LLM request timeout in seconds    |

`CHAT_MODEL` defaults to `qwen2.5:7b` for Ollama and `claude-opus-5-5` for Anthropic. OpenAI has no default and needs `CHAT_MODEL`; the application refuses to start without it. The model must support tool calling.

`OPENAI_BASE_URL` points the OpenAI provider at any API that implements Chat Completions with tool calling, such as Azure OpenAI, vLLM or Groq.

The Generator does the retries for every provider, so the OpenAI and Anthropic SDKs' own retries are turned off. With Anthropic models that support it, refused requests are rerun on a fallback model by the API (server-side refusal fallbacks).

Example:

```yaml
environment:
  LLM_PROVIDER: ollama
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
* DateDiff tool
* Support tools and the SQLite store
* Evaluation checks and runner

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
│   ├── generator.py        Retries and backoff around the provider
│   ├── logging.py          Request ID logging
│   ├── models.py           Shared models
│   ├── providers/          Ollama, OpenAI and Anthropic adapters
│   ├── static/index.html   Demo chat UI
│   ├── tool_registry.py    Tool registration
│   └── tool_validator.py   Tool argument validation
│
├── tools/
│   ├── base.py             Tool interface
│   ├── calculator.py       Calculator tool
│   ├── date_diff.py        Days between two dates
│   ├── datetime_tool.py    Date and time tool
│   └── support.py          Customer, order, policy and ticket tools
│
├── business/
│   ├── seed.py             Demo customers, orders and policies
│   └── store.py            SQLite store
│
├── docs/
│   ├── architecture.md
│   └── deployment.md
│
├── evaluation/
│   ├── datasets/           Labelled evaluation cases
│   ├── results/            Evaluation reports per model
│   ├── checks.py           Tool, answer and verification checks
│   ├── runner.py           Repeated runs and aggregation
│   ├── report.py           Markdown and JSON reports
│   └── tools.py            Fixed-clock datetime tool
│
├── tests/
│   ├── test_agent.py
│   ├── test_api.py
│   ├── test_calculator.py
│   ├── test_cloud_providers.py
│   ├── test_config.py
│   ├── test_date_diff.py
│   ├── test_datetime_tool.py
│   ├── test_e2e.py
│   ├── test_evaluation_checks.py
│   ├── test_evaluation_runner.py
│   ├── test_executor.py
│   ├── test_generator.py
│   ├── test_models.py
│   ├── test_providers.py
│   ├── test_support_tools.py
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
├── ruff.toml
├── LICENSE
└── README.md
```

---

# Current Scope

The support scenario runs on demo data in SQLite. It does not currently include:

* Connectors to real systems (CRM, order management, ticketing)
* Document retrieval over real policy documents
* Authentication and authorization
* Conversation persistence on the server (the client keeps the conversation)

The architecture is designed so these capabilities can be introduced as additional tools or services without changing the agent loop.

---

# Evaluation

The `evaluation/` package measures the agent against labelled cases with a real model, so changes to tools, prompts or models can be compared with numbers.

The bundled dataset, [`evaluation/datasets/agent_cases.jsonl`](evaluation/datasets/agent_cases.jsonl), has 30 cases in eight categories: no tool needed, single tool, date questions, chained tools, multi-step calculations, self-correction, rejected requests and customer support. The support cases check order status, late deliveries, return windows, policy answers, an ambiguous customer name, that no ticket is opened when none was asked for, and that one is opened when it was. Each case is run several times, because the same question can pass in one run and fail in the next.

During evaluation the `datetime` tool is replaced by one that always reports `2026-10-17T09:00:00Z`, so answers such as "69 days until Christmas" stay stable. The support tools use the same clock and a fresh copy of the demo data.

### Metrics

- **Pass:** tool selection and the answer check both pass
- **Tool selection:** every required tool is called and no tool outside the allowed set
- **Answer:** the expected number appears in the answer (within a tolerance), or one of the expected phrases does; for rejection cases, a tool rejected the request and nothing succeeded afterwards
- **Tool-verified:** the expected number was produced by a tool, not stated by the model

### Running the evaluation

The evaluation uses `LLM_PROVIDER` and `CHAT_MODEL` unless `--provider` and `--model` are given. With Ollama running and the model pulled:

```powershell
docker compose exec agent-api python -m evaluation
docker compose exec agent-api python -m evaluation --model llama3.1:8b --repeats 5
docker compose exec agent-api python -m evaluation --categories chain date
```

With an API key in `.env`, the same cases run against a cloud model:

```powershell
docker compose exec agent-api python -m evaluation --provider openai --model <model>
docker compose exec agent-api python -m evaluation --provider anthropic
```

Reports are written to `evaluation/results/<model>.md` and `.json`, including a trace of the first failing run of each case. Inside the container they are not on a mounted volume; copy them out with:

```powershell
docker compose cp agent-api:/app/evaluation/results ./evaluation/
```

### Results: qwen2.5:7b

These results were recorded before the support tools and the support system prompt were added, with the 21 general cases.

21 cases, 3 runs each, after each change. Reports: [baseline](evaluation/results/qwen2.5-7b-baseline.md), [+ weekday](evaluation/results/qwen2.5-7b-weekday.md), [+ date_diff](evaluation/results/qwen2.5-7b.md).

| Category | Baseline | + weekday in datetime | + date_diff tool |
|---|---|---|---|
| **Overall pass** | 73% | 81% | **86%** |
| **Overall tool-verified** | 51% | 59% | **74%** |
| No tool | 100% | 100% | 100% |
| Single tool | 100% | 100% | 100% |
| Date | 67% | 89% | 78% |
| Chained tools | 17% | 33% | **67%** |
| Chained tools, tool-verified | 0% | 0% | **50%** |
| Multi-step | 83% | 100% | 100% |
| Self-correction | 100% | 100% | 100% |
| Rejection | 50% | 50% | 50% |

Each column changes one thing. The effects that can be attributed to a change:

- **Weekday in the datetime result:** the weekday question went from 0/3 to 3/3. Before, the model named the wrong day in every run (Sunday, Friday, Friday).
- **`date_diff` tool:** the two day-count questions went from 0/3 and 1/3 to 3/3 each. In those runs the model called `datetime` and then `date_diff` with the right dates, so the answers are tool-verified instead of the model's own arithmetic ("89 days until Christmas" before, 69 now). The model did not call `date_diff` for any other case. A later run with 5 repeats per case (see below) puts the day-count pass rate at 7/10, so the tool is a clear improvement but not a guarantee.

With 3 runs per case a single run moves a case by 33 points, so smaller differences are within run-to-run variation.

### Model comparison: qwen2.5:7b vs llama3.1:8b

Same code, tools, cases and fixed clock; only the model changes. 21 cases, 3 runs each. Reports: [qwen2.5:7b](evaluation/results/qwen2.5-7b.md), [llama3.1:8b](evaluation/results/llama3.1-8b.md).

| Category | qwen2.5:7b | llama3.1:8b |
|---|---|---|
| **Overall pass** | **86%** | **43%** |
| **Overall tool-verified** | **74%** | **49%** |
| No tool | 100% | 11% |
| Single tool | 100% | 100% |
| Date | 78% | 67% |
| Chained tools | 67% | 0% |
| Multi-step | 100% | 67% |
| Self-correction | 100% | 0% |
| Rejection | 50% | 17% |

What the llama3.1:8b runs show:

- **It does not answer without tools when tools are offered.** "Say hello in Turkish" got "I don't have the required function", and "Explain what an API is" was sent to the calculator as prose.
- **It ignores the tool's date.** With `datetime` returning 2026, it answered "It's 2024" in every run, and passed the literal string `"datetime"` to `date_diff` as a start date.
- **It writes corrected tool calls as text.** After a tool error, the next call appears inside the answer, for example `{"name": "calculator", "parameters": {"expression": "2**10"}}`, instead of as a native tool call, so the agent treats it as the final answer. This explains most of the 0% in self-correction. It is a failure to follow the tool calling format; parsing tool calls out of text as a fallback could recover part of it.

Single-tool calculations and the weekday question passed every run with both models, so those results do not depend on the model. qwen2.5:7b remains the default. The gap is large enough that more runs would not reverse it; latency is not compared because the llama3.1 run had less free memory.

### Tried and rejected: a prompt rule for the date

The model sometimes answered "2023" for "What year is it?" without calling `datetime`. A system-prompt rule was tested to address it:

> The datetime tool returns the real current date and time. Call it for any question about the current date, day or year, and trust its result even if it is later than you would expect from your training data.

The full evaluation looked positive at first: "What year is it?" went from 1/3 to 3/3 and overall pass rose from 86% to 89% ([report](evaluation/results/qwen2.5-7b-trust-prompt.md)). Tool-verified answers fell from 74% to 64%, though, so the date and chain cases were rerun with 5 repeats each, with and without the rule ([without](evaluation/results/targeted-date-chain-prompt-b.md), [with](evaluation/results/targeted-date-chain-prompt-c.md)):

| Date and chain cases, 5 runs each | Without the rule | With the rule |
|---|---|---|
| "What year is it?" | 4/5 | 4/5 |
| Day-count cases | 7/10 | 3/10 |
| `date_diff` used in day-count cases | 7/10 | 3/10 |
| Chain cases, tool-verified | 35% | 15% |

The improvement on the year question was run-to-run variation; with more runs both prompts score 4/5. The cost was real: the rule pushed the model towards repeated `datetime` calls, sometimes until the step limit, and away from `date_diff`. The rule was not adopted.

What the evaluation shows:

- **Simple tool use is reliable.** Every single-tool calculation passed, and every answer came from the calculator.
- **The model guesses what the tools do not provide.** Weekdays and date differences were wrong until a tool returned them. Adding a small tool helped more than asking the model to reason, and more than a prompt rule.
- **The model does not fully trust the tools' date.** For "What year is it?" it sometimes answers "2023" without calling `datetime` (4/5 passing with 5 runs), and some "25 years from now" answers start with "If today is October 17, 2023". A prompt rule against this did not help (see below).
- **Time-of-day arithmetic is still unsolved.** "How many hours are left until the end of today?" passed 0/3 in the last run; no tool covers it and the model answered "no hours left".
- **Correct is not the same as verified.** Self-correction cases pass every time, but in half of the runs the model states the corrected value after the error instead of calling the calculator again.
- **The rejection safeguard works when it is reached.** `2 ** 5000000` was rejected and explained in every run. For `10 ** 2000` the model wrote `10^2000`, got a fixable error, and stopped instead of retrying, so the request never reached the size limit.

The answer checks are lexical: a case passes if the expected number appears anywhere in the answer. The dataset is small and hand-written, so the results are a regression baseline for this project, not a general benchmark.

---

# Known Limitations

* **Model reasoning.** The loop supports chaining tools, and this is covered by tests, but `qwen2.5:7b` rarely uses it: chained-tool cases pass 67% of the time (see Evaluation), and questions that need time-of-day arithmetic still fail. Day counts became reliable once a `date_diff` tool existed; without a matching tool the model still does the arithmetic itself.
* **Unverified final steps.** After a tool error, the model often states the corrected result without calling the tool again; only half of the self-correction runs were tool-verified.
* **Thread-based timeouts.** A timed-out tool keeps running in its worker thread. Tools bound their own work, but full isolation would need a separate process per call.

---

# Future Improvements

Possible next steps include:

* Document search over real policy documents (Agentic RAG)
* Connectors to real CRM, order and ticketing systems
* Authentication and authorization
* Streaming responses
* Tracing and observability
* Fallback parsing for tool calls written as text, then a re-run of the llama3.1 comparison
* Process-isolated tool execution

---

# License

This project is licensed under the MIT License. See the `LICENSE` file for details.
