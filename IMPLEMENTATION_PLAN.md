# Implementation Plan

This plan follows `SPEC.md` for v0: a small educational Python coding agent for single-file competitive programming tasks. The implementation must stay explicit and readable, must not use LangChain, LangGraph, or any other agent framework, and must use only Python plus the official OpenAI SDK for model calls.

## Global Constraints

- Runtime model server: OpenAI or a local Responses API-compatible server, via the official OpenAI Python SDK.
- Required environment variable: `OPENAI_API_KEY`.
- Optional environment variables: `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_TIMEOUT_SECONDS`, and `OPENAI_MAX_RETRIES`.
- Default model constant: `DEFAULT_MODEL = "gpt-5-mini"` unless changed deliberately in code.
- Exposed model tools in `solve` mode: exactly `list_files`, `read_file`, `write_solution`, and `run_tests`.
- Exposed model tools in `advise` mode: exactly `list_files`, `read_file`, and `run_tests`.
- No arbitrary shell tool, network tool, package installation tool, Git integration, subagents, memory, GUI, web app, or database.
- The agent may read only `statement.md`, `solution.py`, and `tests/*.in` / `tests/*.out` inside the selected task directory.
- The agent may write only `solution.py`, with `.solution.py.bak` created before replacement.
- Tests must be runnable without calling the OpenAI API by using a fake model client.

## Milestone 1: Project Skeleton and CLI Validation

### Goal

Create the package shape and a CLI that validates environment and task structure before any model call exists.

### Files to Create or Modify

- Modify `pyproject.toml`
  - Align package metadata with `cp-agent` / import package `cp_agent`.
  - Add source layout configuration.
  - Add runtime dependency on `openai`.
  - Add test tooling dependency/configuration if needed.
- Create `README.md`
  - Document setup, `OPENAI_API_KEY`, `OPENAI_MODEL`, demo command, and test commands.
- Create `AGENTS.md`
  - Use the repository-specific instructions suggested in `SPEC.md`.
- Create `src/cp_agent/__init__.py`
- Create `src/cp_agent/__main__.py`
- Create `src/cp_agent/cli.py`
- Create `tests/`
- Create initial test helpers/fixtures if useful, for example `tests/conftest.py`.

### Tests Required

- CLI exits non-zero with the exact helpful message when `OPENAI_API_KEY` is missing.
- CLI rejects a missing task directory without calling any model client.
- CLI rejects a task missing `statement.md`.
- CLI rejects a task missing `solution.py`.
- CLI rejects a task missing `tests/`.
- CLI rejects a task with no matching `.in` / `.out` pairs.
- CLI accepts a structurally valid task and reaches the placeholder "not implemented yet" path without calling OpenAI.

### Done Criteria

- `python -m cp_agent solve <task_dir>` is importable and reaches `cli.py`.
- Supported flags exist: `--max-iterations`, `--timeout-seconds`, `--trace-file`, and `--verbose`.
- Environment validation happens before task validation that would start the agent.
- Task validation happens before any OpenAI API call.
- Error messages are readable for a workshop participant.
- No model loop, tools, or test runner behavior is implemented beyond validation scaffolding.

## Milestone 2: Test Discovery and Local Test Runner

### Goal

Implement deterministic local execution of `solution.py` against paired sample tests.

### Files to Create or Modify

- Create `src/cp_agent/test_runner.py`
- Modify `src/cp_agent/cli.py` only if a temporary internal validation/demo command path is needed.
- Create `tests/test_test_runner.py`

### Tests Required

- Discovers sorted matching `.in` / `.out` pairs under `tests/`.
- Ignores or reports unmatched files in a predictable, readable way.
- Passing solution returns `ok: true`, `all_passed: true`, and a correct summary.
- Wrong-answer solution returns failed result with expected and actual output.
- Runtime-error solution captures non-zero exit code and bounded stderr.
- Syntax-error solution captures failure details.
- Timeout solution returns `exit_code: null`, `error: "timeout"`, and bounded runtime.
- Output comparison normalizes trailing whitespace per line and final trailing newlines.
- Captured stdout and stderr respect `max_stdout_chars` and `max_stderr_chars`.

### Done Criteria

- `test_runner.py` runs `python solution.py` with test input passed via stdin, not through arbitrary shell access.
- Every test execution has a timeout.
- Results match the JSON-friendly shape required by `FR-009`.
- Test output is deterministic enough for trace logging and final summaries.
- Unit tests cover pass, fail, runtime error, syntax error, timeout, and whitespace normalization.

## Milestone 3: Safe Workspace and Tool Layer

### Goal

Implement the bounded filesystem wrapper and the exact four tools exposed to the model.

### Files to Create or Modify

- Create `src/cp_agent/workspace.py`
- Create `src/cp_agent/tools.py`
- Modify `src/cp_agent/test_runner.py` if needed to consume workspace-safe paths.
- Create `tests/test_workspace.py`
- Create `tests/test_tools.py`

### Tests Required

- Real path resolution keeps all reads and writes inside the task root.
- Blocks `../secrets.txt`, absolute paths such as `/etc/passwd`, user paths such as `~/.ssh/id_rsa`, and symlinks that resolve outside the task root.
- `list_files` returns only relative file paths inside the task directory.
- `read_file` can read allowed files and returns `{ "ok": true, "path": ..., "content": ... }`.
- `read_file` rejects missing or disallowed files with `{ "ok": false, "error": ... }`.
- `read_file` truncates oversized files and includes a warning.
- `write_solution` replaces only `solution.py`.
- `write_solution` creates `.solution.py.bak` before writing.
- `write_solution` preserves UTF-8.
- Tool schemas include clear names, descriptions, JSON schema parameters, explicit `required`, `additionalProperties: false`, and `strict: true`.
- Tool dispatch rejects unknown tools and invalid arguments.
- `run_tests` tool returns the test runner result without exposing shell access.

### Done Criteria

- The model-facing tool registry contains exactly `list_files`, `read_file`, `write_solution`, and `run_tests`.
- No model-provided path can escape the task directory after real-path resolution.
- No model-provided arguments can write anywhere except `solution.py`.
- Tool outputs are JSON-serializable and bounded by configured limits.
- Unit tests prove both allowed and blocked paths.

## Milestone 4: Trace Logging and Verbose Progress

### Goal

Add trace JSONL and human-readable progress so model/tool loop behavior is observable without calling the OpenAI API in tests.

### Files to Create or Modify

- Create `src/cp_agent/trace.py`
- Modify `src/cp_agent/cli.py`
- Modify `src/cp_agent/agent.py` so trace events are emitted around model requests, model responses, tool calls, tool results, test summaries, and final status.
- Modify `src/cp_agent/tools.py` only if tool-result summarization needs local helper support.
- Create `tests/test_trace.py`
- Extend `tests/test_agent_loop_fake_model.py` and `tests/test_cli_validation.py` to verify trace files are written during fake-model runs.

### Tests Required

- Default trace path is `trace.jsonl`.
- `--trace-file` overrides the trace path.
- Each trace line is one valid JSON object.
- Trace records model request, model response, tool call, tool result, test summary, and final events.
- Tool result trace events summarize outputs rather than logging full file contents or large stdout/stderr payloads.
- Trace does not include `OPENAI_API_KEY` or other environment secrets.
- Verbose mode prints workshop-friendly progress for model requests, tool calls, test summaries, solution writes, success, and failure.
- Verbose tool-call output uses a short form like `I am using <tool> because <reason>`, where the reason comes from the model's required public `reason` tool argument rather than hidden model reasoning.
- The final concise result remains at the end of terminal output.
- Non-verbose mode keeps output concise.

### Done Criteria

- Trace writer can append events throughout the CLI, tool layer, and agent loop.
- Secret redaction is covered by tests.
- Fake-model integration tests prove trace output without OpenAI.
- Verbose output format is stable enough for live demo narration and includes model-supplied public tool-use reasons.
- Trace and verbose plumbing are present without needing the OpenAI API.

## Milestone 5: Fake Agent Loop

### Goal

Implement the full explicit agent loop using an injectable fake model client before adding OpenAI.

### Files to Create or Modify

- Create `src/cp_agent/agent.py`
- Create `src/cp_agent/prompts.py`
- Modify `src/cp_agent/cli.py`
- Modify `src/cp_agent/tools.py` as needed for loop dispatch.
- Create `tests/test_agent_loop_fake_model.py`

### Tests Required

- Fake model flow:
  - `read_file(statement.md)`
  - `read_file(solution.py)`
  - `run_tests()`
  - `write_solution(correct_code)`
  - `run_tests()`
  - final answer
- Agent stops with success when `run_tests` reports all tests passed.
- Agent stops with failure when `max_iterations` is reached.
- Agent appends tool outputs back into conversation state.
- Agent handles invalid tool names and invalid tool arguments with structured tool errors.
- Agent handles model final answer without tool calls.
- Agent records trace events for model requests, tool calls, tool results, test summaries, and final status.
- Agent returns enough structured result data for the CLI final output.

### Done Criteria

- The loop visibly follows `SPEC.md`: initialize messages/tools, call model, execute tool calls, append outputs, stop on final answer, success, or max iterations.
- The loop is easy to explain in a workshop and avoids unnecessary abstractions.
- Fake-model integration proves the architecture with no OpenAI API key and no network call.
- Final CLI output can print success and failure examples in the required shape.

## Milestone 6: OpenAI SDK Integration

### Goal

Add the real OpenAI model wrapper while keeping it thin and replaceable by the fake client in tests.

### Files to Create or Modify

- Create `src/cp_agent/openai_client.py`
- Modify `src/cp_agent/agent.py`
- Modify `src/cp_agent/cli.py`
- Modify `src/cp_agent/tools.py` if schema shape must match the selected OpenAI SDK API exactly.
- Modify `README.md`
- Optionally create `tests/test_openai_client.py` for pure response parsing helpers.
- Optionally create `tests/test_live_openai_smoke.py`, skipped unless `RUN_OPENAI_SMOKE=1`.

### Tests Required

- Model name comes from `OPENAI_MODEL` when set.
- Model name falls back to the single default constant when unset.
- OpenAI client receives exactly the four tool schemas.
- OpenAI client converts model tool calls into the internal tool-call representation.
- OpenAI client converts final model text into the internal final-answer representation.
- API errors are caught and returned or raised in a workshop-friendly way for the CLI to display.
- Optional live smoke test is skipped by default and runs only with `RUN_OPENAI_SMOKE=1`.

### Done Criteria

- Real model usage goes only through the official OpenAI Python SDK.
- No LangChain, LangGraph, or external agent framework dependency is introduced.
- Tests for the normal suite still do not require `OPENAI_API_KEY`.
- The OpenAI wrapper stays thin: request creation, response parsing, and error translation only.
- README clearly explains `OPENAI_API_KEY`, `OPENAI_MODEL`, and the optional live smoke test.

## Milestone 7: Demo Examples and End-to-End Polish

### Goal

Add the workshop demo tasks and make the full command work against `two_sum_bug`.

### Files to Create or Modify

- Create `examples/two_sum_bug/statement.md`
- Create `examples/two_sum_bug/solution.py`
- Create `examples/two_sum_bug/tests/sample1.in`
- Create `examples/two_sum_bug/tests/sample1.out`
- Create `examples/two_sum_bug/tests/sample2.in`
- Create `examples/two_sum_bug/tests/sample2.out`
- Create `examples/dijkstra_bug/statement.md`
- Create `examples/dijkstra_bug/solution.py`
- Create `examples/dijkstra_bug/tests/sample1.in`
- Create `examples/dijkstra_bug/tests/sample1.out`
- Create `examples/dijkstra_bug/tests/sample2.in`
- Create `examples/dijkstra_bug/tests/sample2.out`
- Modify `README.md`
- Extend or create end-to-end tests that use fake clients and example directories.

### Tests Required

- `examples/two_sum_bug` validates as a task directory.
- `examples/two_sum_bug` initially has failing tests.
- Fake agent can repair a copied `two_sum_bug` fixture and reach success.
- `examples/dijkstra_bug` validates as a task directory.
- Test suite confirms examples have matching `.in` / `.out` pairs.
- Optional live smoke test can run `python -m cp_agent solve examples/two_sum_bug` when explicitly enabled.

### Done Criteria

- `two_sum_bug` is the default recommended demo in README.
- `dijkstra_bug` exists as a second, more advanced example.
- End-to-end fake-model tests prove the agent can read, run tests, write `solution.py`, rerun tests, and stop.
- CLI success output includes status, iterations, tests passed, and modified file.
- CLI failure output includes status, reason, iterations, tests passed, and last failure where available.

## Milestone 8: Advisor Mode Refinement

### Goal

Add a read-only coaching mode that gives students a guided hint instead of editing `solution.py`.

### Files to Create or Modify

- Modify `src/cp_agent/cli.py`
- Modify `src/cp_agent/agent.py`
- Modify `src/cp_agent/prompts.py`
- Modify `src/cp_agent/tools.py`
- Extend fake-model, CLI, and OpenAI-wrapper tests.
- Update `SPEC.md`, `README.md`, and `docs/agent_workflow.md`.

### Tests Required

- `advise <task_dir>` validates `OPENAI_API_KEY` and task shape like `solve`.
- `advise` accepts `--max-iterations`, `--timeout-seconds`, `--trace-file`, and `--verbose`.
- Advisor mode exposes only `list_files`, `read_file`, and `run_tests`.
- Advisor mode returns success when the model returns final advice text, even if tests fail.
- Advisor mode does not stop early when tests pass before advice is produced.
- A hallucinated `write_solution` call in advisor mode returns a structured tool error and does not modify files.
- Existing `solve` tests still prove solution repair works.

### Done Criteria

- `uv run python -m cp_agent advise tasks/<name> --verbose` returns a guided hint.
- Advisor output prints an `Advice:` block followed by the compact final summary.
- Advisor mode never prints `Modified: solution.py`.
- Advisor mode cannot expose or execute `write_solution`.
- Trace and verbose output still work in both modes.

## Milestone 9: Final Verification and Review Pass

### Goal

Verify the v0 done criteria and remove accidental complexity before considering the implementation complete.

### Files to Create or Modify

- Modify any previously created source, tests, examples, or docs only for fixes.
- No new architecture files unless a previous milestone exposed a concrete need.

### Tests Required

- Run the full unit test suite.
- Run the fake-model integration test.
- Run `python -m cp_agent solve examples/two_sum_bug` with a real OpenAI API key, if available and explicitly intended.
- Run the CLI error paths manually or through tests:
  - missing `OPENAI_API_KEY`,
  - invalid task directory,
  - missing tests,
  - max iterations reached.
- Run a source scan or dependency check confirming no LangChain, LangGraph, or other agent framework was added.

### Done Criteria

- All `SPEC.md` v0 done criteria are satisfied.
- The normal test suite passes without `OPENAI_API_KEY`.
- Optional live smoke remains opt-in.
- The code is small, explicit, and suitable for explaining to high school competitive programmers.
- Runtime dependencies are limited to the official OpenAI SDK plus Python standard library.
- Test-only dependencies, if any, are clearly separated from runtime dependencies.
- README gives a complete workshop demo path.

## Milestone 10: Local Qwen Through Unsloth

### Goal

Prepare a local Qwen trial that needs only the Unsloth API key, using the existing
Responses client, agent loop, and bounded tools.

### Files to Create or Modify

- Extend `openai_client.py` with explicit endpoint, timeout, retry configuration,
  single-loaded-model discovery, and actionable API errors.
- Update `cli.py` to identify the selected model in verbose mode.
- Add `.env.qwen.example`, an ignored local `.env.qwen`, and a shared PyCharm
  advisor run configuration reading that file. The local preset pins the model
  ID `unsloth/Qwen3.8-27B-GGUF` from the supplied Unsloth catalog; discovery remains
  an optional fallback.
- Update `SPEC.md`, `README.md`, and `docs/agent_workflow.md`.
- Extend client and CLI tests without making network calls.

### Tests Required

- Configuration is passed to the official SDK; omitted options keep SDK defaults.
- Invalid timeout/retry settings fail before any model request.
- Automatic discovery selects the sole loaded model, ignores cached unloaded
  models, and reports missing, ambiguous, or unauthenticated model lists.
- An SDK transport test verifies local request routing, bearer authentication,
  Responses function-call replay, and final advice without modifying a task.
- Existing solver and advisor tests continue to pass.
- The prepared entry point reports a missing key without starting inference.

### Done Criteria

- The user can fill in only `.env.qwen`'s API key and launch the Qwen advisor preset.
- No cloud API key, server key, or inference request is needed for preparation.
- Live model quality and tool calling remain explicitly unverified until the trial.

## Risks and Ambiguities

- `pyproject.toml` currently uses project name `cpagent`, while `SPEC.md` names the project `cp-agent` and the import package `cp_agent`. The implementation should choose one packaging name deliberately, most likely distribution `cp-agent` with import package `cp_agent`.
- `pyproject.toml` currently requires Python `>=3.14`, but `SPEC.md` only says Python. Python 3.14 may be too new for workshop machines; this should be confirmed before implementation.
- `SPEC.md` says the agent may read `statement.md`, `solution.py`, and `tests/*.in` / `tests/*.out`, while `list_files` generally lists files in the task directory. The implementation should decide whether `list_files` lists all in-root files or only allowed task files; stricter allowed task files better matches v0 safety.
- `read_file` says to limit and truncate large files, but does not define the exact warning field. Use a stable shape such as `{"ok": true, "truncated": true, "warning": "...", ...}` and document it in tests.
- `run_tests` says normalize trailing whitespace per line and final trailing newlines. The exact normalization helper should be shared by expected and actual output and covered by focused tests.
- `write_solution` creates `.solution.py.bak`; the spec does not say whether to overwrite an existing backup on later writes. A simple v0 behavior is to overwrite the backup with the immediately previous `solution.py` before each write.
- `trace.jsonl` should be written to the CLI-provided path, resolved relative to the process working directory when relative. Starting a run may replace the previous trace file at that path; this should be documented in README and tests should avoid polluting example task directories.
- Verbose "because" messages should not expose hidden chain-of-thought. They should be short operational explanations supplied in the model's required public `reason` tool argument, such as reading the statement to understand the task or running tests to verify the current solution.
- `FR-010` allows either asking the model for a final explanation after passing tests or stopping with success. For simplicity and reliability, v0 can stop with success immediately after all tests pass, optionally preserving the latest model text if available.
- The OpenAI SDK has multiple API surfaces. The implementation should pick one official, current surface and keep conversion isolated in `openai_client.py` so tests can fake it.
- The spec allows an optional live smoke test but requires normal tests to avoid OpenAI. CI and local default test commands must skip live tests unless `RUN_OPENAI_SMOKE=1`.
- Test execution uses local Python subprocesses only. The command should use `sys.executable` rather than a hard-coded `python` for portability, while still matching the behavior described by the spec.
- The examples should be designed so sample tests are sufficient for the workshop demo, but the agent may overfit visible tests. This is acceptable for v0 because hidden-test simulation is listed as a future extension.
