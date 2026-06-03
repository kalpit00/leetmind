# Leetmind architecture

Leetmind is a small agentic system for learning tool calling. The guiding rule:
**the LLM only ever sees sanitized JSON from tools** — never the database, the
network, or your LeetCode credentials.

## Layers

```
LeetCode Authenticated GraphQL Client   leetmind/leetcode/
        ↓   (sanitized dataclasses)
Local SQLite Cache                       leetmind/db/
        ↓
Keyword Search Engine (FTS5 + scoring)   leetmind/search/
        ↓
Knowledge Base (offline LLM analysis)    leetmind/kb/
        ↓
Agent Tools (sanitized JSON)             leetmind/tools/
        ↓
Agent (OpenAI Agents SDK)                leetmind/agent/
        ↓
CLI Chat Interface                       leetmind/cli/
```

### 1. LeetCode client (`leetmind/leetcode/`)
- `client.py` is the **only** module that reads `LEETCODE_SESSION` / `LEETCODE_CSRF`
  and the only one that performs network calls. Secrets live on a private
  `httpx.Client` and never leave this layer.
- `queries.py` holds the GraphQL operations (schema is undocumented; update here
  if LeetCode changes things).
- `types.py` are sanitized dataclasses (`Problem`, `ProblemList`, `Submission`,
  `SubmissionDetail`) — no auth fields.

### 2. SQLite cache (`leetmind/db/`)
- `schema.sql`: `problems`, `lists`, `list_problems`, `submissions`, `sync_meta`,
  the FTS5 table `search_docs`, and the knowledge-base tables
  `solution_analyses`, `problem_bridges`, plus the FTS5 table `pattern_docs`.
- `repositories.py`: thin data-access objects (`ProblemsRepo`, `ListsRepo`,
  `SubmissionsRepo`, `MetaRepo`, `AnalysesRepo`, `BridgesRepo`). No SQL leaks
  above this layer.

### 3. Sync (`leetmind/sync/`)
- `sync_problems` → full catalog + your solved status.
- `sync_lists` → your private lists and membership.
- `sync_submissions` → submissions per solved problem, plus code for the most
  recent Accepted submission (throttled, bounded by `--limit`).

### 4. Keyword search (`leetmind/search/`)
- `rebuild_index` denormalizes each problem (title, topics, lists, languages,
  notes, code) into the FTS5 table.
- `search` uses FTS5 to get candidates, then `scoring.py` re-ranks with
  field-aware weights:

| Signal | Weight |
| --- | --- |
| exact problem ID | +10 |
| exact slug | +8 |
| accepted submission (solved) | +6 |
| list name match | +5 |
| topic tag match | +4 |
| notes match | +3 |
| code keyword match | +2 |
| title fuzzy match | +1 |

### 5. Knowledge Base (`leetmind/kb/`)
The KB distills accepted submissions into reusable problem-solving memory.

- `analyzer.py`: offline LLM pass run by `leetmind analyze-solutions`. For each
  accepted submission with code, it extracts:
  - pattern name
  - core idea
  - invariant
  - complexity
  - pitfalls
  - reusable template code
  - technique labels
  - observable coding-style traits
- `pattern_search.py`: rebuilds and queries `pattern_docs`, an FTS5 index over
  the distilled analyses.
- `style_profile.py`: aggregates recurring style traits and technique usage.
- `bridge.py`: connects a target problem to already-solved problems whose
  pattern/template transfers to it. This powers flows like
  "Maximal Rectangle -> Largest Rectangle in Histogram".

The KB is persistent but local. It is rebuilt incrementally using `code_hash` and
`analysis_version`, so unchanged submissions are skipped on repeated analysis.

### 6. Tools (`leetmind/tools/`)
Plain, framework-free functions returning sanitized dicts:
`resolve_problem`, `get_my_lists`, `get_problems_in_list`, `get_my_submissions`,
`get_submission_details`, `search_my_solutions`,
`get_solution_pattern`, `search_solution_patterns`, `get_coding_style_profile`,
`bridge_problem_to_my_solutions`.

### 7. Agent (`leetmind/agent/`)
- `system_prompt.py`: behavior + tool-use guidance.
- `tool_registry.py`: wraps the tool functions with `function_tool` (schemas are
  derived from type hints + docstrings).
- `agent.py`: builds the `Agent` and runs it (`ask_once`, `Conversation`).

### 8. CLI (`leetmind/cli/main.py`)
`sync`, `status`, `analyze-solutions`, `kb-status`, `ask`, `chat`, `search`,
`patterns`, `bridge`.

## Why tools instead of raw data?

The agent learns *what* to ask, not *how* to fetch. A typical multi-step trace:

1. User: "Did I solve Largest Rectangle in Histogram with a monotonic stack?"
2. Agent → `resolve_problem("Largest Rectangle in Histogram")` → topics include
   "Monotonic Stack", `solved: true`.
3. Agent → `get_my_submissions("largest-rectangle-in-histogram")` → finds an
   Accepted Java submission with code.
4. Agent → `get_submission_details("123456789")` → inspects the code/notes for a
   stack-based approach.
5. Agent answers, citing the evidence.

This is the layered tool-calling behavior the project is built to demonstrate.
The cache makes repeated calls cheap and deterministic.

## Why the KB matters

The MVP could answer "did I solve X?" and "what submissions do I have?". The KB
adds "how does X relate to what I already know?".

Example:

1. User: "Help me solve Maximal Rectangle using what I've already solved."
2. Agent -> `bridge_problem_to_my_solutions("Maximal Rectangle")`.
3. Bridge tool finds analyzed solved problems with transferable patterns:
   - `Largest Rectangle in Histogram`
   - `Maximal Square`
   - `Count Submatrices With All Ones`
4. Tool returns relationships, shared patterns, transfer steps, and the user's
   own reusable template code.
5. Agent explains the bridge: build a histogram for each matrix row, then reuse
   the user's monotonic-stack histogram template.

That turns Leetmind from a profile lookup agent into a personal problem-solving
memory layer.
