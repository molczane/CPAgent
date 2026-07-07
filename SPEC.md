# SPEC-001: Minimal Python Coding Agent for Competitive Programming Tasks

## Status

Draft v0.1

## Project name

`cp-agent`

## Purpose

Build a small educational coding agent in Python that can solve or repair simple competitive-programming-style tasks by using an OpenAI model, local file tools, and test feedback.

The goal is not to build a production coding assistant. The goal is to create a clear workshop demo that shows how coding agents work under the hood:

```text
read problem -> inspect code -> run tests -> observe failure -> edit solution -> rerun tests -> stop
```

The implementation should be simple, readable, and suitable for explaining to high school competitive programmers.

## Core idea

The agent is an explicit loop around an LLM:

```text
LLM + tools + local test feedback + bounded workspace = coding agent
```

The model does not directly access the filesystem or terminal. Instead, the Python application exposes a small set of safe tools.

## Main user story

As a workshop participant, I want to run a command like:

```bash
python -m cp_agent solve examples/two_sum_bug
```

and watch the agent:

1. read the task statement,
2. inspect the current solution,
3. run tests,
4. observe failures,
5. edit the solution,
6. rerun tests,
7. stop when all tests pass or when the iteration limit is reached.

As a student who wants a nudge instead of an automatic fix, I also want to run:

```bash
python -m cp_agent advise examples/two_sum_bug
```

and receive a guided hint without the agent modifying `solution.py`.

## Target audience

The code should be understandable for students who know basic Python and competitive programming concepts.

Avoid unnecessary abstractions. Prefer explicit code over clever framework usage.

## Technology assumptions

* Implementation language: Python.
* Required API provider: OpenAI only.
* Required secret: `OPENAI_API_KEY`.
* Optional environment variable: `OPENAI_MODEL`.
* No LangChain or LangGraph in v0.
* No external agent framework in v0.
* Use the official OpenAI Python SDK.
* Use local files and local Python subprocesses only.

## Recommended default model behavior

The implementation should read the model name from:

```bash
OPENAI_MODEL
```

If it is not set, use a single default constant in code, for example:

```python
DEFAULT_MODEL = "gpt-5-mini"
```

The README should clearly say that the model can be changed by setting `OPENAI_MODEL`.

## Scope for v0

The first version supports simple single-file Python competitive programming tasks.

A task directory has this shape:

```text
task_name/
  statement.md
  solution.py
  tests/
    sample1.in
    sample1.out
    sample2.in
    sample2.out
```

In `solve` mode, the agent may modify:

```text
solution.py
```

The agent may read:

```text
statement.md
solution.py
tests/*.in
tests/*.out
```

The agent may not modify tests in v0.

## Non-goals for v0

Do not implement these in the first version:

* multi-file projects,
* C++/Java/Kotlin solution support,
* internet access,
* package installation,
* arbitrary shell access,
* Git integration,
* subagents,
* long-term memory,
* GUI,
* web app,
* LangChain,
* LangGraph,
* database storage,
* solving tasks from online judges directly.

These can be future extensions.

## Functional requirements

### FR-001: CLI entrypoint

The project must provide a CLI command:

```bash
python -m cp_agent solve <task_dir>
```

It must also provide a read-only advisor command:

```bash
python -m cp_agent advise <task_dir>
```

Optional flags:

```bash
--max-iterations 5
--timeout-seconds 2
--trace-file trace.jsonl
--verbose
```

Example:

```bash
python -m cp_agent solve examples/dijkstra_bug --max-iterations 5 --verbose
python -m cp_agent advise examples/dijkstra_bug --max-iterations 5 --verbose
```

### FR-002: Environment validation

On startup, the CLI must check that `OPENAI_API_KEY` is set.

If the key is missing, print a helpful error:

```text
OPENAI_API_KEY is not set.
Set it with:
export OPENAI_API_KEY="..."
```

Then exit with a non-zero status.

### FR-003: Task validation

Before starting the agent loop, validate that the task directory contains:

```text
statement.md
solution.py
tests/
```

The `tests/` directory must contain at least one matching `.in` / `.out` pair.

For example:

```text
sample1.in
sample1.out
```

If validation fails, print a readable error and do not call the OpenAI API.

### FR-004: Safe workspace boundary

All file operations must be restricted to the selected task directory.

The agent must not be able to read or write files outside the task directory, even if it requests paths like:

```text
../secrets.txt
/etc/passwd
~/.ssh/id_rsa
```

Path handling must resolve real paths and verify that every target path remains inside the task root.

### FR-005: Available tools

In `solve` mode, expose exactly these tools to the model:

```text
list_files
read_file
write_solution
run_tests
```

In `advise` mode, expose only read-only/advisory tools:

```text
list_files
read_file
run_tests
```

`write_solution` must not be exposed in `advise` mode. The agent loop must also reject a `write_solution` tool call in `advise` mode if a malformed or fake model response still requests it.

No arbitrary shell tool should be exposed in v0.

### FR-006: `list_files`

Purpose:

Allow the agent to understand the task directory.

Input:

```json
{}
```

Output:

```json
{
  "files": [
    "statement.md",
    "solution.py",
    "tests/sample1.in",
    "tests/sample1.out"
  ]
}
```

The tool should only list files inside the task directory.

### FR-007: `read_file`

Purpose:

Allow the agent to inspect the statement, solution, and tests.

Input:

```json
{
  "path": "statement.md"
}
```

Output on success:

```json
{
  "ok": true,
  "path": "statement.md",
  "content": "..."
}
```

Output on failure:

```json
{
  "ok": false,
  "error": "File not found or not allowed"
}
```

The implementation should limit file size. If a file is too large, return a truncated version with a warning.

### FR-008: `write_solution`

Purpose:

Allow the agent to replace `solution.py`.

Input:

```json
{
  "content": "import sys\n..."
}
```

Behavior:

* Replace only `solution.py`.
* Do not allow writing arbitrary paths in v0.
* Preserve UTF-8 encoding.
* Create a backup before writing:

```text
.solution.py.bak
```

Output:

```json
{
  "ok": true,
  "path": "solution.py",
  "bytes_written": 1234
}
```

### FR-009: `run_tests`

Purpose:

Give the agent objective feedback.

Input:

```json
{}
```

Behavior:

For each `tests/*.in` file:

1. Run:

```bash
python solution.py < test.in
```

2. Capture stdout, stderr, exit code, and runtime.
3. Compare stdout to the matching `.out` file.
4. Normalize trailing whitespace per line and final trailing newlines.
5. Mark each test as passed or failed.

Output:

```json
{
  "ok": true,
  "all_passed": false,
  "summary": "1/2 tests passed",
  "results": [
    {
      "name": "sample1",
      "passed": true,
      "exit_code": 0,
      "runtime_ms": 41,
      "expected": "4",
      "actual": "4",
      "stderr": ""
    },
    {
      "name": "sample2",
      "passed": false,
      "exit_code": 0,
      "runtime_ms": 38,
      "expected": "7",
      "actual": "6",
      "stderr": ""
    }
  ]
}
```

If the program times out:

```json
{
  "name": "sample3",
  "passed": false,
  "exit_code": null,
  "runtime_ms": 2000,
  "error": "timeout"
}
```

### FR-010: Agent loop

The `solve` loop should follow this structure:

```text
initialize messages
initialize tools
for iteration in range(max_iterations):
    call model with current context and tools

    if model returns final answer:
        stop

    if model returns tool calls:
        execute each tool call locally
        append tool outputs to conversation
        if run_tests reports all tests passed:
            ask model for final explanation or stop with success

if max iterations reached:
    stop with failure summary
```

The `advise` loop uses the same model/tool/output pattern, but with the read-only tool set. It succeeds when the model returns final advice text. It may run tests for feedback, but it must not stop merely because tests pass; it should continue until it can print the advice or until `max_iterations` is reached.

The loop must be visible and easy to explain in the workshop.

### FR-011: System prompt

`solve` mode must use a system prompt similar to:

```text
You are a competitive programming coding agent.

Your goal is to make solution.py pass all provided tests.

You may use the available tools to inspect files, run tests, and replace solution.py.

Work iteratively:
1. Read the statement.
2. Read the current solution.
3. Run the tests.
4. If tests fail, reason about the bug or missing algorithm.
5. Replace solution.py with a corrected version.
6. Run tests again.

Rules:
- Do not modify tests.
- Do not assume internet access.
- Do not ask the user for clarification.
- Prefer simple, correct algorithms.
- Keep the solution readable.
- Stop when all tests pass.
```

`advise` mode must use a separate coaching prompt that tells the model to inspect the task with read-only tools, return a guided hint, avoid full replacement code, and never modify files.

The exact prompts may evolve, but the mode-specific behavior above is required.

### FR-012: Final result

At the end, print a concise result:

Success example:

```text
Status: success
Iterations: 3
Tests: 4/4 passed
Modified: solution.py
```

Failure example:

```text
Status: failed
Reason: max iterations reached
Iterations: 5
Tests: 2/4 passed
Last failure: sample3 expected 10 but got 9
```

Advisor success example:

```text
Advice:
Focus on sorting the presentations by finish time. Keep the first presentation
that starts after the last chosen one, and compare that idea with the failing
sample before changing code.

Status: success
Iterations: 3
Tests: 1/2 passed
```

Advisor mode must never print `Modified: solution.py`.

### FR-013: Trace logging

The agent must write a trace file in JSONL format. The CLI flag:

```bash
--trace-file trace.jsonl
```

selects the trace path and defaults to:

```text
trace.jsonl
```

Relative trace paths are resolved from the process working directory. Starting a run may replace the existing trace file at that path.

Each event should be one JSON object per line.

Example events:

```json
{"type": "model_request", "iteration": 1}
{"type": "model_response", "iteration": 1, "tool_calls": ["read_file"], "final": false}
{"type": "tool_call", "iteration": 1, "tool": "read_file", "args": {"path": "statement.md", "reason": "I need to understand the task statement"}}
{"type": "tool_result", "iteration": 1, "tool": "read_file", "result": {"ok": true, "path": "statement.md"}}
{"type": "tool_call", "iteration": 2, "tool": "run_tests", "args": {"reason": "I need test feedback before editing"}}
{"type": "test_summary", "iteration": 2, "passed": 1, "total": 2, "summary": "1/2 tests passed", "all_passed": false}
{"type": "final", "status": "success", "iterations": 3, "tests_passed": 2, "tests_total": 2, "modified": true}
```

Trace output is for observability, not for reconstructing every byte of context. Tool results should be summarized enough to inspect the loop while avoiding large file contents, large stdout/stderr payloads, and other noisy data. Do not log the OpenAI API key or any environment secrets; secret-like fields must be redacted.

### FR-014: Human-readable verbose mode

If `--verbose` is enabled, print progress while preserving the concise final result at the end.

Verbose output should narrate model-requested tool steps in a workshop-friendly form:

```text
[1] I am using read_file(statement.md) because I need to understand the task statement.
[1] I am using read_file(solution.py) because I need to inspect the current solution.
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

The reason text should be short and operational: it explains the tool's role in the loop, not the model's private reasoning. Each model-facing tool schema must require a public `reason` string argument. The application uses that public `reason` for verbose output, truncating or falling back to a generic reason if the field is malformed. Do not expose hidden chain-of-thought or ask the model to reveal long reasoning just for verbose logs.

Older acceptable progress style:

```text
[1] Model requested read_file(statement.md)
[1] Model requested read_file(solution.py)
[2] Running tests...
[2] Tests: 1/2 passed
[3] Updating solution.py
[4] Running tests...
[4] Tests: 2/2 passed
```

This is important for the live workshop demo because students should be able to follow the loop as it happens.

## Architecture

Recommended package layout:

```text
cp-agent/
  pyproject.toml
  README.md
  SPEC.md
  AGENTS.md
  src/
    cp_agent/
      __init__.py
      __main__.py
      cli.py
      agent.py
      openai_client.py
      tools.py
      workspace.py
      test_runner.py
      prompts.py
      trace.py
  examples/
    two_sum_bug/
      statement.md
      solution.py
      tests/
        sample1.in
        sample1.out
        sample2.in
        sample2.out
    dijkstra_bug/
      statement.md
      solution.py
      tests/
        sample1.in
        sample1.out
        sample2.in
        sample2.out
  tests/
    test_workspace.py
    test_test_runner.py
    test_tools.py
    test_agent_loop_fake_model.py
```

## Module responsibilities

### `cli.py`

Responsible for:

* argument parsing,
* environment validation,
* task directory validation,
* creating the agent,
* printing final output.

### `agent.py`

Responsible for:

* the main agent loop,
* maintaining conversation state,
* calling the OpenAI client,
* dispatching tool calls,
* stopping conditions.

### `openai_client.py`

Responsible for:

* wrapping OpenAI SDK usage,
* creating model requests,
* parsing model responses,
* returning either final text or tool calls.

Keep this wrapper thin.

### `tools.py`

Responsible for:

* tool definitions,
* tool schemas,
* mapping tool names to Python functions.

### `workspace.py`

Responsible for:

* path normalization,
* workspace-boundary checks,
* safe reads,
* safe writes,
* file listing.

### `test_runner.py`

Responsible for:

* discovering `.in` / `.out` pairs,
* running `solution.py`,
* timeout handling,
* stdout comparison,
* returning structured test results.

### `trace.py`

Responsible for:

* JSONL trace writing,
* redacting secrets,
* recording model/tool/test events.

### `prompts.py`

Responsible for:

* system prompt,
* initial user message template.

## Tool schema requirements

Each tool definition must have:

* clear name,
* clear description,
* JSON schema parameters,
* `additionalProperties: false`,
* required fields listed explicitly.

Example conceptual schema:

```json
{
  "type": "function",
  "name": "read_file",
  "description": "Read a UTF-8 text file inside the task workspace.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path inside the task workspace."
      },
      "reason": {
        "type": "string",
        "description": "One short public sentence explaining why this tool is useful now. Do not include hidden chain-of-thought."
      }
    },
    "required": ["path", "reason"],
    "additionalProperties": false
  },
  "strict": true
}
```

The local tool dispatcher strips the public `reason` argument before calling the local tool implementation. The reason is for observability only; it must not expand the tool's filesystem or process permissions.

## Test strategy

The implementation must be testable without calling the OpenAI API.

### Unit tests

Add tests for:

1. workspace path safety,
2. file listing,
3. allowed file reading,
4. blocked path traversal,
5. `write_solution`,
6. test discovery,
7. test runner pass/fail behavior,
8. timeout behavior,
9. tool dispatch,
10. trace writing,
11. trace secret redaction.

### Fake model integration test

Create a fake model client that simulates tool calls.

Example fake flow:

```text
read_file(statement.md)
read_file(solution.py)
run_tests()
write_solution(correct_code)
run_tests()
final_answer("All tests pass.")
```

This proves the agent loop works without using the OpenAI API.

### Optional live smoke test

Add one test or script that uses the real OpenAI API, but skip it by default unless explicitly enabled.

Example:

```bash
RUN_OPENAI_SMOKE=1 pytest tests/test_live_openai_smoke.py
```

## Example task: `two_sum_bug`

Use a simple task where the correct solution is easy to verify.

### Statement

Given `n`, target `x`, and an array of `n` integers, print two 1-based indices whose values sum to `x`, or print `IMPOSSIBLE`.

### Buggy solution idea

The initial `solution.py` contains an O(n²) solution with an off-by-one bug or wrong index printing.

This is a good first demo because the agent can fix it quickly.

## Example task: `dijkstra_bug`

Use this only after the simpler demo works.

### Statement

Given a weighted directed graph with non-negative edge weights, compute the shortest distance from node `1` to node `n`.

### Buggy solution idea

The initial `solution.py` may contain one of these bugs:

* uses BFS instead of Dijkstra,
* initializes distances incorrectly,
* treats graph as undirected when it is directed,
* uses zero-based indexing incorrectly.

This is more interesting for competitive programmers, but less reliable as the first live demo.

## Safety requirements

The v0 agent must be intentionally limited.

Required safety rules:

1. No arbitrary shell tool.
2. No network access tool.
3. No package installation.
4. No file writes except `solution.py`.
5. No reads outside the task directory.
6. Timeout every test execution.
7. Limit captured stdout and stderr.
8. Limit number of agent iterations.
9. Never log secrets.
10. Validate all model-requested tool arguments.

## Default limits

Use these defaults:

```text
max_iterations = 5
per_test_timeout_seconds = 2
max_file_read_chars = 20000
max_tool_output_chars = 30000
max_stdout_chars = 10000
max_stderr_chars = 10000
```

The CLI may allow overriding some of these, but safe defaults should be used.

## Error handling

The agent should handle:

* missing `OPENAI_API_KEY`,
* invalid task directory,
* missing tests,
* model API errors,
* invalid tool call arguments,
* file permission errors,
* syntax errors in `solution.py`,
* runtime errors in `solution.py`,
* test timeouts,
* max iteration reached.

Errors should be shown in a workshop-friendly way.

## Done criteria for v0

The implementation is done when:

1. `python -m cp_agent solve examples/two_sum_bug` works.
2. The agent can read the task statement and solution.
3. The agent can run tests.
4. The agent can replace `solution.py`.
5. The agent stops when tests pass.
6. The agent stops after `max_iterations`.
7. It cannot read files outside the task directory.
8. It cannot write files outside `solution.py`.
9. `advise` mode can inspect the task and return a guided hint without modifying files.
10. `advise` mode does not expose or execute `write_solution`.
11. Unit tests pass.
12. A fake-model integration test proves the loop works without OpenAI.
13. README explains setup and demo usage.
14. The code is simple enough to explain during a workshop.

## Recommended implementation order

### Milestone 1: Project skeleton

Create:

```text
pyproject.toml
README.md
SPEC.md
src/cp_agent/
tests/
examples/
```

Add a working CLI that validates inputs but does not call the model yet.

### Milestone 2: Test runner

Implement local test discovery and execution.

Command should work internally:

```text
run solution.py against tests/*.in and compare with tests/*.out
```

Add unit tests.

### Milestone 3: Safe workspace tools

Implement:

```text
list_files
read_file
write_solution
run_tests
```

Add path-safety tests.

### Milestone 4: Fake agent loop

Implement the full agent loop using a fake model client.

This proves the architecture before using the OpenAI API.

### Milestone 5: OpenAI integration

Implement real OpenAI tool calling.

The model should be able to request tools, receive outputs, and continue.

### Milestone 6: Demo examples

Add:

```text
examples/two_sum_bug
examples/dijkstra_bug
```

Make `two_sum_bug` the default workshop demo.

### Milestone 7: Trace and verbose output

Add JSONL trace logging and readable terminal progress.

### Milestone 8: Advisor mode

Add `python -m cp_agent advise <task_dir>` as a read-only coaching mode.

Advisor mode should use read-only tools, return guided hint text, and preserve
the current `solve` behavior unchanged.

## Suggested `AGENTS.md` for this repository

Create an `AGENTS.md` file with these instructions:

```text
# AGENTS.md

## Project goal

This repository implements a minimal educational coding agent for competitive programming tasks.

The goal is clarity, not production complexity.

## Engineering principles

- Keep the code simple and readable.
- Prefer explicit control flow over clever abstractions.
- Do not introduce LangChain, LangGraph, or another agent framework in v0.
- Use only the official OpenAI Python SDK for model calls.
- Keep all local file operations inside the selected task directory.
- Do not add arbitrary shell access in v0.
- Write tests before or alongside implementation.

## Done means

- Unit tests pass.
- Fake-model integration test passes.
- The example task can be solved with the real OpenAI API when `OPENAI_API_KEY` is set.
- The CLI output is understandable for a live workshop demo.
```

## Future extensions

After v0 works, possible extensions include:

1. C++ solution support.
2. `run_command` with a strict allowlist.
3. LangGraph implementation of the same workflow.
4. More CP tasks.
5. Test generation.
6. Hidden-test simulation.
7. Patch-based editing instead of full-file replacement.
8. Context summarization.
9. Subagents for “solver” and “reviewer.”
10. Web UI for classroom demos.
