# Enterprise AI Agent

A simple AI agent project built with FastAPI, Ollama, and tools.

The application first evaluates a user's question with the Planner. When a
tool is needed, it runs the appropriate tool and uses the LLM to turn the
result into a clear answer for the user.

## Features

- FastAPI-based `/chat` API
- Local LLM support through Ollama
- Calculator and DateTime tools
- JSON Schema validation for tool arguments
- Recovery attempt when a tool fails
- Retry and backoff for Ollama calls
- Request validation
- API, Ollama, and model readiness checks
- Test suite

## Requirements

- Docker Desktop
- Docker Compose

## Start the application

Build and start the containers in the background:

```powershell
docker compose up -d --build
```

The default model is `llama3`. On the first setup, download it into the
Ollama container:

```powershell
docker compose exec ollama ollama pull llama3
```

The application runs at:

```text
http://localhost:8000
```

## Health endpoints

### Is the API running?

```powershell
curl.exe -i http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

This endpoint only confirms that the API is running.

### Are Ollama and the configured model ready?

```powershell
curl.exe -i http://localhost:8000/ready
```

When the model is ready:

```json
{
  "status": "ready"
}
```

If Ollama is unavailable or the configured model has not been downloaded,
the endpoint returns `503 Service Unavailable`.

## Chat endpoint

Send a question with:

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

The `question` field:

- Cannot be blank or contain only whitespace.
- Can contain at most 4,000 characters.

Invalid requests are rejected with `422 Unprocessable Entity`.

## Tools

### Calculator

Evaluates mathematical expressions.

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

```json
{
  "tool": "datetime",
  "arguments": {}
}
```

## Retry behavior

The project has two separate retry settings:

| Setting | Default | Description |
| --- | ---: | --- |
| `MAX_RETRIES` | `3` | Number of retries for technical Ollama/LLM failures |
| `RETRY_BASE_DELAY` | `1.0` | Initial delay between LLM retries, in seconds |
| `TOOL_MAX_RETRIES` | `1` | Number of correction attempts after a tool failure |

With `TOOL_MAX_RETRIES: 1`, the flow is:

1. The tool runs once.
2. If it fails, the Planner receives the error and tries to produce a corrected tool call.
3. The corrected tool call runs at most one more time.

To use a different value with Docker Compose, add it to the `agent-api`
`environment` section in `docker-compose.yml`:

```yaml
TOOL_MAX_RETRIES: 2
```

Then rebuild the API container:

```powershell
docker compose up -d --build agent-api
```

## Tests

Run the full test suite inside the running API container:

```powershell
docker compose exec agent-api python -m pytest -q
```

For detailed output:

```powershell
docker compose exec agent-api python -m pytest -v
```

## Project structure

```text
app/
  api.py           FastAPI endpoints
  config.py        Environment variables and settings
  generator.py     Ollama and LLM calls
  planner.py       Tool selection and argument validation
  executor.py      Tool execution
  pipeline.py      Planning, tool execution, and recovery flow
  tool_registry.py Tool registration

tools/
  base.py          Tool interface
  calculator.py    Calculator tool
  datetime_tool.py Date and time tool

tests/
  ...              Unit and API tests
```

## Stop the application

```powershell
docker compose down
```

To remove the Ollama volume and its downloaded models as well:

```powershell
docker compose down -v
```

This command removes the downloaded Ollama models.
