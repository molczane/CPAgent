# AGENTS.md

## Project goal

This repository implements a minimal educational coding agent for competitive programming tasks.

The source of truth is SPEC.md.

## Hard constraints

- Use Python.
- Use the official OpenAI Python SDK only.
- Do not use LangChain, LangGraph, AutoGen, CrewAI, or other agent frameworks in v0.
- Do not add arbitrary shell access in v0.
- Do not add network access.
- The agent may only modify solution.py inside the selected task directory.
- Keep the implementation simple and readable for a workshop audience.

## Development workflow

Before implementing a milestone:
1. read SPEC.md,
2. read IMPLEMENTATION_PLAN.md,
3. identify the relevant milestone,
4. implement only that milestone,
5. add or update tests,
6. run the relevant test command,
7. summarize what changed and what remains.

## Done means

A change is done only when:
- relevant tests pass,
- behavior matches SPEC.md,
- no unnecessary framework or abstraction was introduced,
- CLI behavior is understandable for a live workshop demo.

## IDE workflow via MCP

Prefer the connected JetBrains IDE's MCP tools for code navigation, symbol-aware
refactoring, inspections, and running existing configurations. Pass this
checkout's absolute root as `projectPath` on every IDE call. Tool names below
refer to the available `mcp__pycharm__` tools; inspect the current tool schemas
instead of assuming arguments or capabilities from another session.

- Read the relevant local skill below before starting that workflow. Load only
  the skills needed for the task.
- Inspect worktree changes before editing and preserve existing user work.
  The restrictions on CPAgent's generated solutions above describe the product;
  repository development may edit source, tests, and documentation as requested.
- For unfamiliar code, begin with `context search` as described by the host
  instructions, then use IDE symbol lookup and focused file reads. For a known
  file or symbol, navigate directly.
- Use `get_project_status` before inspections. If indexing is incomplete, treat
  missing results as inconclusive; use source inspection while it finishes.
- Prefer `rename_refactoring` for symbol renames. Check the resulting diff for
  reference updates and unintended edits.
- Verify suspected unresolved symbols with `get_symbol_info` and
  `get_file_problems`; text search alone does not prove a resolution failure.
- Before Python toolchain commands, use the available `python-tools` skill and
  `get_python_environment` for a file in the relevant module. Use the returned
  interpreter and package manager; do not hard-code a Python version or venv.
- Keep verification local by default. Existing SOLVE/ADVISE configurations can
  call a model and modify task files; select them only when the requested task
  includes a live run. Do not print environment secrets from configuration data.
- If an IDE operation is unsupported or unavailable, report that limitation and
  use a focused file/terminal fallback. Never claim an IDE refactoring or debugger
  session happened when only a text edit or normal run occurred.
- Summarize changed behavior and actual checks, distinguishing successful tests
  from incomplete IDE diagnostics. Do not treat a generic build success as proof
  that Python tests passed.

### Local IDE skills

| Workflow | Skill |
| --- | --- |
| Navigate symbols, dependencies, and calls | [ide-navigate](.agents/skills/ide-navigate/SKILL.md) |
| Edit code and refactor symbols | [ide-edit](.agents/skills/ide-edit/SKILL.md) |
| Run tests and inspect changed files | [ide-verify](.agents/skills/ide-verify/SKILL.md) |
| Reproduce and diagnose runtime failures | [ide-debug](.agents/skills/ide-debug/SKILL.md) |
| Review a diff with IDE evidence | [ide-review](.agents/skills/ide-review/SKILL.md) |
