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

## Run The Agent

This repository includes sample tasks in `tasks/`. Each task has an intentionally wrong `solution.py`, so the agent has something concrete to repair.

From the repository root, run the agent through uv:

```bash
uv run python -m cp_agent solve tasks/double_number --verbose
```

Supported flags:

```bash
--max-iterations 5
--timeout-seconds 2
--trace-file trace.jsonl
--verbose
```

The CLI validates the task directory, constructs the OpenAI SDK-backed model client, and runs the local tool loop. The model can only use the four safe tools from `SPEC.md`: `list_files`, `read_file`, `write_solution`, and `run_tests`.

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

`OPENAI_API_KEY` is required. `OPENAI_MODEL` is optional; if it is not set, the code uses its default model constant.

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
