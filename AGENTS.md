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