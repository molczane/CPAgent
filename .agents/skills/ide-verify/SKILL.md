---
name: ide-verify
description: Verify code changes with JetBrains MCP inspections, Python environment discovery, and focused test or run configurations.
---

# Verify changes through the IDE

Use the checkout root as `projectPath` and the repository's `AGENTS.md` workflow.

## Environment and execution

Before Python toolchain commands, consult the available `python-tools` skill and
call `get_python_environment` on a Python file in the target module. Use its
`executablePath` and `packageManager`. If it reports no interpreter, follow its
specific guidance; `configure_python_interpreter` is appropriate only when that
response recommends it. Never guess a replacement interpreter.

Use `get_run_configurations` to discover existing configurations. With `filePath`,
it can discover test run points; pass a returned 1-based line and file path to
`execute_run_configuration` for a focused test. Use launch overrides only when
`supportsDynamicLaunchOverrides` is true and the override is needed. Do not print
configuration environment values, which may contain credentials.

Choose the narrowest meaningful regression tests. CPAgent's local unittest suite
can be run with the returned interpreter, `-B -m unittest discover -s tests`.
Use `execute_terminal_command` or a shell execution tool when no suitable IDE
configuration exists. Check the repository's documented test command first.
Keep live model smoke tests opt-in; ordinary verification must not run a model.
A timeout is not a pass: inspect available output and process state before rerunning.

## IDE diagnostics

Check `get_project_status` before analysis. Use `get_file_problems` for one file
or `lint_files` for changed files. Inspect `timedOut`, `notAnalyzedReason`, and
`more`; empty or partial results do not establish that every file was analyzed.

Call `build_project` after code edits as required by its tool contract. Python
projects may return limited build diagnostics even with `isSuccess=true`; report
that limitation and rely on relevant Python tests and inspections for evidence.
Documentation-only edits need link/format checks rather than a Python build.

Finish with `git diff --check` and report actual test counts, failures, skips,
and any incomplete checks. Do not run broader suites repeatedly after the
relevant checks pass unless a new change or unresolved concern warrants it.
