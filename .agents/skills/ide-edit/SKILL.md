---
name: ide-edit
description: Edit project code and perform symbol refactorings through JetBrains MCP, including reference-aware renames and focused patch review.
---

# Edit and refactor through the IDE

Use the checkout root as `projectPath`. Follow `AGENTS.md` and inspect existing
changes with `git_status` or `git status --short` plus `git diff` before editing.
Read the target and its immediate callers/tests. Preserve unrelated user changes.

## Symbol refactoring

Use `rename_refactoring` for programmatic symbol renames. Supply the source's
project-relative `pathInProject`, the exact `symbolName`, and requested `newName`.
If the target is ambiguous, verify the declaration with `get_symbol_info` first.
Do not replace every textual occurrence of a common identifier.

Inspect the diff after the rename: declaration, imports, constructors, type hints,
and tests should refer to the new symbol. Check string-based lookup, patch targets,
and documentation separately when relevant; automatic reference updates may not
cover them. Preserve related names unless the user requested their rename too.
For example, renaming `Agent` does not imply renaming `AgentConfig` or `AgentResult`.

If the rename times out, inspect state before retrying: it may already have applied.
Do not silently substitute text replacement for an explicitly requested IDE rename.

## Implementation changes

Use IDE `apply_patch` for focused edits and `create_new_file` for new files without
overwriting existing content. Follow nearby patterns. Use `reformat_file` only
when formatting is needed, and inspect for whole-file churn afterward.

Check the diff for accidental changes and run `git diff --check`. Follow
[ide-verify](../ide-verify/SKILL.md) for relevant inspections and tests. For a pure
rename, existing tests normally suffice; add coverage when behavior changes.
Report the files changed, reference updates, and verification results.
