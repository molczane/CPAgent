---
name: ide-navigate
description: Navigate project code and resolved symbols through JetBrains MCP when locating definitions, tracing calls, or investigating dependencies.
---

# Navigate through the IDE

Use the checkout root as `projectPath`. Read the repository's IDE workflow in
`AGENTS.md`; inspect current tool schemas before calling tools.

- For an unfamiliar subsystem, start with `context search` when available, then
  inspect the first relevant path. For a known identifier use `search_symbol`;
  use `search_file` for paths and `search_text` or `search_regex` for literal or
  pattern matches. Scope subsequent searches to the relevant directory.
- Use `list_directory_tree` for structure and `read_file` for focused source
  reads. `get_all_open_file_paths` can supply editor context when the user refers
  to an open file. Open a result with `open_file_in_editor` when useful to the user.
- Use `get_symbol_info` at the reference's 1-based line and column to verify what
  it resolves to. If project symbol search fails for a library identifier, retry
  with `include_external=true` before concluding it is absent.
- For callers or callees, resolve a fully qualified callable name and use
  `analyze_calls` with `INCOMING_CALLS` or `OUTGOING_CALLS`. Start with shallow
  depth and a small node limit; expand returned `treePath` values as needed.
  An unsupported or empty hierarchy is not proof that there are no calls,
  especially with dynamic Python dispatch. Cross-check relevant source and tests.
- Use `get_project_modules` and `get_project_dependencies` when module or library
  ownership matters. Compare IDE metadata with `pyproject.toml` and the lockfile
  for packaging questions; IDE metadata alone is not the packaging contract.

Return concrete file/line evidence and distinguish resolved symbols from
inferences. Navigation alone does not authorize edits or executing the program.
