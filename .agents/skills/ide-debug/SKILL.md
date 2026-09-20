---
name: ide-debug
description: Diagnose runtime failures in a JetBrains project using reproducible test runs, tracebacks, resolved call paths, and debugger tools when exposed.
---

# Diagnose a failure through the IDE

Use the checkout root as `projectPath` and follow `AGENTS.md`. Start from the
reported command/configuration, input, expected behavior, and actual failure.
Inspect existing changes before attributing a regression to the current code.

1. Inspect the failing test or entry point and its launch settings. Follow
   [ide-verify](../ide-verify/SKILL.md) for interpreter discovery and execution.
   Prefer a small deterministic test over a live model call. Do not launch a
   SOLVE configuration merely to investigate an issue: it may modify a task.
2. Capture the traceback, exit status, and relevant output. Use `read_file` and
   `get_symbol_info` at failing frames; use `analyze_calls` for resolved callers
   or callees. Separate environment/import failures from application behavior.
3. Check the actual exposed tool catalog before promising interactive debugging.
   The currently observed connector has run tools but no breakpoint, stepping,
   or variable-inspection tools. `execute_run_configuration` is a normal run;
   the universal `execute_tool` does not imply unlisted debugger support.
4. If a future connector exposes a debugger, read its schemas, use the smallest
   reproducer, inspect paused frames and needed variables, and clean up only
   sessions/breakpoints created for this task. Avoid evaluating expressions with
   side effects or displaying credentials.
5. Without debugger tools, narrow hypotheses using focused tests, existing trace
   output, or minimal temporary instrumentation. Keep logs free of secrets and
   remove instrumentation added for diagnosis. Do not remove the user's logging.
6. When a fix is requested, add an appropriate regression test and make a narrow
   correction. Re-run the reproducer and relevant checks. For investigation-only
   requests, report evidence and the proposed fix without changing production code.

Report the observed cause, evidence connecting it to the failure, and verification.
Label untested hypotheses and live-model behavior that remains unverified.
