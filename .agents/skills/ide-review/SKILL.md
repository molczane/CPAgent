---
name: ide-review
description: Review a requested diff for behavioral regressions using JetBrains MCP symbol resolution, inspections, and call analysis.
---

# Review with IDE evidence

Use the checkout root as `projectPath`. Establish the requested diff/base and
inspect worktree changes. Keep review read-only unless fixes were requested.
Focus on changed paths and concrete regressions rather than style churn.

- Read affected callers and tests with `read_file`; use `search_symbol` and
  `get_symbol_info` to verify types, signatures, and resolved references.
- Before reporting an unresolved import or missing symbol, check IDE readiness
  and `get_file_problems`. If indexing or interpreter setup is incomplete,
  describe the verification gap instead of presenting it as a code defect.
- Use `analyze_calls` for call relationships and inspect dynamic Python paths
  separately. Account for configuration, string-based references, and subprocess
  boundaries when a refactoring changes names or arguments.
- Trace a concrete trigger to its behavioral consequence. For CPAgent changes,
  examine applicable workspace boundaries, solve/advise behavior, bounded tool
  output, and model-response handling rather than inventing unrelated concerns.
- Run relevant local tests when needed, following
  [ide-verify](../ide-verify/SKILL.md). Do not launch live model configurations as
  part of a default review.

Lead with actionable findings, each with a file and 1-based line, trigger,
consequence, and supporting evidence. State when no actionable findings were
found and mention relevant verification gaps. Honor any requested output schema.
