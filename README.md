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

This repository includes a small sample task in `task/`. Its `solution.py` is intentionally wrong, so the agent has something concrete to repair.

From the repository root, run the agent through uv:

```bash
uv run python -m cp_agent solve task --verbose
```

Supported flags:

```bash
--max-iterations 5
--timeout-seconds 2
--trace-file trace.jsonl
--verbose
```

The CLI validates the task directory, constructs the OpenAI SDK-backed model client, and runs the local tool loop. The model can only use the four safe tools from `SPEC.md`: `list_files`, `read_file`, `write_solution`, and `run_tests`.

## Agent Parameters

You can tune the agent from the command line:

```bash
uv run python -m cp_agent solve task \
  --max-iterations 8 \
  --timeout-seconds 3 \
  --trace-file trace.jsonl \
  --verbose
```

Parameters:

- `--max-iterations`: maximum number of model/tool loop iterations before the agent stops. Default: `5`.
- `--timeout-seconds`: timeout for each sample test execution. Default: `2`.
- `--trace-file`: path reserved for JSONL trace output. Default: `trace.jsonl`.
- `--verbose`: prints more progress information during the run.

Model selection is controlled by environment variables:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5-mini"
```

`OPENAI_API_KEY` is required. `OPENAI_MODEL` is optional; if it is not set, the code uses its default model constant.

You can also run through the `.venv` Python after `uv sync` has installed the project:

```bash
.venv/bin/python -m cp_agent solve task --verbose
```

If `.venv/bin/python -m cp_agent ...` says `No module named cp_agent`, run `uv sync` first. If `.venv/bin/python -m pip ...` says `No module named pip`, that is normal for this uv-managed environment; use `uv sync` or `uv run` instead of `python -m pip`.

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
