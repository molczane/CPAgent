# cp-agent

`cp-agent` is a minimal educational coding agent for competitive programming tasks. It is designed as a workshop demo that makes the coding-agent loop visible:

```text
read problem -> inspect code -> run tests -> observe failure -> edit solution -> rerun tests -> stop
```

The project follows `SPEC.md`. Version 0 uses Python and the official OpenAI Python SDK only. It does not use LangChain, LangGraph, or any other agent framework.

## Setup With uv

This project is meant to work well with `uv`. From the repository root, install/sync the editable package and dependencies with:

```bash
uv sync
```

Set the required OpenAI API key:

```bash
export OPENAI_API_KEY="..."
```

The model can be changed with:

```bash
export OPENAI_MODEL="gpt-5-mini"
```

If `OPENAI_MODEL` is not set, the implementation will use its default model constant.

## Local Qwen With Unsloth

The same official OpenAI SDK can connect to Unsloth's local Responses API. Load
Qwen in Unsloth and keep its API server running at `http://127.0.0.1:8888/v1`.

Copy `.env.qwen.example` to `.env.qwen` if that local file does not already exist.
Fill in only `OPENAI_API_KEY` with the **Unsloth API key**. This file is ignored by
Git. The remaining settings are ready:

```dotenv
OPENAI_API_KEY=""
OPENAI_BASE_URL="http://127.0.0.1:8888/v1"
OPENAI_MODEL="unsloth/Qwen3.8-27B-GGUF"
OPENAI_TIMEOUT_SECONDS="3600"
OPENAI_MAX_RETRIES="0"
```

In PyCharm, select **[QWEN ADVISE] cp-agent: club_fair_schedule** and run it. The
shared configuration reads `.env.qwen` and does not inherit the parent process's
OpenAI settings. It prints the selected model before starting the agent loop.

For a solver run, select **[QWEN SOLVE] cp-agent: double_number**. It uses the same
`.env.qwen` settings, can edit `tasks/double_number/solution.py`, and writes its
trace to `trace-qwen-solve-double_number.jsonl`.

For the same run in a terminal, use a subshell to load the local settings without
changing your normal OpenAI configuration:

```bash
(
  set -a
  source .env.qwen
  uv run python -m cp_agent advise tasks/club_fair_schedule \
    --max-iterations 10 --timeout-seconds 3 \
    --trace-file trace-qwen-advice.jsonl --verbose
)
```

The preset pins `unsloth/Qwen3.8-27B-GGUF`, the model ID from the Unsloth catalog
shown in DeepSeek Harness, and skips model discovery. `Qwen3.8-27B` is its display
name, rather than the API model ID.

Optionally, `OPENAI_MODEL=auto` queries `/v1/models` after authentication and
selects the single model marked `loaded: true`. Cached but unloaded models are
ignored. Multiple loaded models or servers without a `loaded` marker require
an explicit model ID.

The preset allows up to 3600 seconds of HTTP inactivity per model request and
disables automatic retries, since local generation can be slow. This is separate
from `--timeout-seconds`, which limits each sample test. Both `solve` and `advise`
use the same model settings; the first trial uses the read-only advisor prompt.
Solver trials also require the coding-agent solver prompt to be active if you
have switched it to a workshop demo variant.

Compatibility requires `/v1/responses` with structured function calls and tool
results; Chat Completions compatibility alone is insufficient. Although the
DeepSeek Harness preset uses `openai-completions`, the configured Unsloth server
also exposes `/v1/responses` and translates it internally to Chat Completions.
CPAgent therefore keeps its Responses client. Local tools still run in CPAgent.
Normal tests use fake responses and an in-memory SDK transport;
actual Qwen tool calling and answer quality must be checked during the live trial.

## Run The Agent

This repository includes sample tasks in `tasks/`. Each task has an intentionally wrong `solution.py`, so the agent has something concrete to repair.

From the repository root, run solver mode through uv:

```bash
uv run python -m cp_agent solve tasks/double_number --verbose
```

To get a guided hint without modifying `solution.py`, run advisor mode:

```bash
uv run python -m cp_agent advise tasks/club_fair_schedule --verbose
```

Supported flags:

```bash
--max-iterations 5
--timeout-seconds 2
--trace-file trace.jsonl
--verbose
```

The CLI validates the task directory, constructs the OpenAI SDK-backed model client, and runs the local tool loop. In `solve` mode, the model can use the four safe tools from `SPEC.md`: `list_files`, `read_file`, `write_solution`, and `run_tests`. In `advise` mode, the model only gets `list_files`, `read_file`, and `run_tests`.

For a deeper explanation of the architecture, loop, tool boundary, and tracing, see [Agent Workflow](docs/agent_workflow.md).

## Agent Parameters

You can tune the agent from the command line:

```bash
uv run python -m cp_agent solve tasks/double_number \
  --max-iterations 8 \
  --timeout-seconds 3 \
  --trace-file trace.jsonl \
  --verbose
```

Parameters:

- `--max-iterations`: maximum number of model/tool loop iterations before the agent stops. Default: `5`.
- `--timeout-seconds`: timeout for each sample test execution. Default: `2`.
- `--trace-file`: path for JSONL trace output. Default: `trace.jsonl`.
- `--verbose`: prints step-by-step tool narration during the run.

The same flags work with `advise`:

```bash
uv run python -m cp_agent advise tasks/club_fair_schedule \
  --max-iterations 5 \
  --timeout-seconds 3 \
  --trace-file advice-trace.jsonl \
  --verbose
```

Verbose mode keeps the final compact summary at the end, but adds readable lines while the loop is running:

```text
[1] I am using read_file(statement.md) because I need to understand the task statement.
[2] I am using run_tests() because test feedback tells me what is failing.
[2] Tests: 1/2 passed
[3] I am using write_solution because I have a candidate fix for solution.py.
[4] I am using run_tests() because I need to verify the updated solution.
[4] Tests: 2/2 passed
Status: success
Iterations: 4
Tests: 2/2 passed
Modified: solution.py
```

Advisor mode prints a hint first, then keeps the compact final summary at the end:

```text
Advice:
Sort presentations by finish time, then greedily keep the next one that starts
after the last chosen presentation. Compare that idea with the failing sample.

Status: success
Iterations: 3
Tests: 1/2 passed
```

Advisor mode is read-only: it cannot call or execute `write_solution`.

The "because" text comes from a required public `reason` argument in each model tool call. It is meant to explain the agent workflow, not reveal hidden model reasoning.

The trace file is useful for inspecting what happened after a run. Each line is one JSON object. For example:

```bash
cat trace.jsonl
```

To see only tool calls:

```bash
uv run python -c 'import json; [print(e["iteration"], e["tool"], e["args"]) for e in map(json.loads, open("trace.jsonl")) if e["type"] == "tool_call"]'
```

Model selection is controlled by environment variables:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5-mini"
```

`OPENAI_API_KEY` is required and belongs to the configured model server.
`OPENAI_MODEL` is optional; if it is not set, the code uses its default model
constant. `OPENAI_BASE_URL` selects a compatible server, including its `/v1` path.
`OPENAI_TIMEOUT_SECONDS` must be finite and positive, and `OPENAI_MAX_RETRIES`
must be a nonnegative integer. If omitted, timeout and retry settings retain the
SDK defaults. `OPENAI_MODEL=auto` requires an explicit `OPENAI_BASE_URL`.

You can also run through the `.venv` Python after `uv sync` has installed the project:

```bash
.venv/bin/python -m cp_agent solve tasks/double_number --verbose
```

If `.venv/bin/python -m cp_agent ...` says `No module named cp_agent`, run `uv sync` first. If `.venv/bin/python -m pip ...` says `No module named pip`, that is normal for this uv-managed environment; use `uv sync` or `uv run` instead of `python -m pip`.

## Sample Tasks

All demo tasks live under `tasks/`:

- `tasks/double_number`: a tiny warm-up task for checking that the agent loop works.
- `tasks/club_fair_schedule`: a greedy interval scheduling task about choosing school club presentations.
- `tasks/contest_hall_maze`: a grid BFS shortest-path task about navigating a contest hall.

Example commands:

```bash
uv run python -m cp_agent solve tasks/double_number --verbose
uv run python -m cp_agent solve tasks/club_fair_schedule --max-iterations 8 --verbose
uv run python -m cp_agent advise tasks/club_fair_schedule --max-iterations 5 --verbose
uv run python -m cp_agent solve tasks/contest_hall_maze --max-iterations 8 --timeout-seconds 3 --verbose
```

## Task Shape

A task directory must contain:

```text
statement.md
solution.py
tests/
  sample1.in
  sample1.out
```

At least one matching `.in` / `.out` pair is required.

## Tests

Run the current validation tests with:

```bash
uv run python -m unittest discover -s tests
```
