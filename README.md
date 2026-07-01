# cp-agent

`cp-agent` is a minimal educational coding agent for competitive programming tasks. It is designed as a workshop demo that makes the coding-agent loop visible:

```text
read problem -> inspect code -> run tests -> observe failure -> edit solution -> rerun tests -> stop
```

The project follows `SPEC.md`. Version 0 uses Python and the official OpenAI Python SDK only. It does not use LangChain, LangGraph, or any other agent framework.

## Setup

Create and activate a Python environment, then install the project and its dependencies:

```bash
python -m pip install -e .
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

From the repository root, run:

```bash
python -m cp_agent solve task --verbose
```

Supported flags:

```bash
--max-iterations 5
--timeout-seconds 2
--trace-file trace.jsonl
--verbose
```

The CLI validates the task directory, constructs the OpenAI SDK-backed model client, and runs the local tool loop. The model can only use the four safe tools from `SPEC.md`: `list_files`, `read_file`, `write_solution`, and `run_tests`.

If you are using the checked-in virtual environment on this machine, the command is:

```bash
.venv/bin/python -m cp_agent solve task --verbose
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
python -m unittest discover -s tests
```
