# Demo

## Setup

```bash
uv sync
cp .env.example .env
# Paste your real LEETCODE_SESSION, LEETCODE_CSRF, and MODEL_API_KEY into .env
uv run leetmind sync --limit 50   # quick first run; omit --limit for full sync
uv run leetmind status            # confirm what got cached
```

> The first full submission sync is slow (one+ throttled request per solved
> problem). Use `--limit N` for a quick demo, or `--skip-submissions` to skip
> code/submission data entirely.

## Build the knowledge base

After submissions with code are synced, analyze them into persistent pattern
memory:

```bash
uv run leetmind analyze-solutions
uv run leetmind embed-kb
uv run leetmind kb-status
```

Example after a full local sync:

```text
Knowledge base:
  analyses       1910
  indexed        1910
  embeddings     1910
  cached bridges 3
  languages      Java(1902), MySQL(4), TypeScript(2), JavaScript(1), Go(1)
  top techniques array, dynamic programming, greedy, string manipulation, sorting, two pointers, hash table, counting
```

## Screenshot script (copy-paste, in order)

Each block maps to a placeholder image in the README. `ask` prints the live
`orchestration:` trace by default — that's the part worth capturing.

```bash
# 01-technique.png  -> 3-tool chain: resolve -> submissions -> details
uv run leetmind ask "Did I solve Two Sum, and if so what data structure did my actual solution use?"

# 02-recommend.png  -> resolve the anchor, then keyword-search your history
uv run leetmind ask "Recommend 2 problems similar to Valid Parentheses I've solved"

# 03-list.png       -> agent finds the list slug, then fetches members
uv run leetmind ask "What are the first 3 problems in my Sliding Window list?"

# 04-status-search.png -> the cache + raw search engine (no LLM)
uv run leetmind status
uv run leetmind search "monotonic stack" --limit 5
```

Example trace (Two Sum technique question):

```text
you: Did I solve Two Sum, and if so what data structure did my actual solution use?
orchestration:
  step 1  call  resolve_problem(query=Two Sum)
           result  found=True, problem='Two Sum' solved=True
  step 2  call  get_my_submissions(problem_slug=two-sum)
           result  count=7
  step 3  call  get_submission_details(submission_id=1309944337)
           result  found=True
answer:
Yes, you solved Two Sum (Problem #1). Your solution used a HashMap ...
```

## More prompts to try

```bash
uv run leetmind ask "Have I solved problem 84?"
uv run leetmind ask "Which of my solved problems use a monotonic stack?"
uv run leetmind ask "Help me solve Maximal Rectangle using what I've already solved"
uv run leetmind ask "What's my coding style?"
uv run leetmind chat            # interactive, keeps conversation history
uv run leetmind ask "..." --quiet   # hide the trace, answer only
```

## Inspecting the search engine directly (no LLM)

```bash
uv run leetmind search "monotonic stack" --limit 5
```

Prints ranked matches with scoring reasons, e.g.:

```json
[
  {
    "title": "Largest Rectangle in Histogram",
    "id": "84",
    "score": 20,
    "matchedOn": ["solved (accepted)", "list name match", "topic tag match", "notes match", "code keyword match"]
  }
]
```

## Inspecting the knowledge base directly

```bash
uv run leetmind patterns "monotonic stack"
uv run leetmind semantic-patterns "matrix rows become histograms"
uv run leetmind bridge "Maximal Rectangle" --refresh
```

`patterns` searches distilled solution analyses by keyword. `semantic-patterns`
searches the same KB by meaning using embeddings plus a small field-aware
reranker over pattern names, techniques, core ideas, and invariants. `bridge`
connects a target problem to already-solved problems whose pattern/template
transfers to it. Use `--refresh` when you want to ignore a cached bridge and
recompute candidates after changing the retrieval layer. For example, Maximal
Rectangle bridges strongly to Largest Rectangle in Histogram:

```text
relationship: build a histogram for each matrix row, then use the monotonic-stack
histogram template from Largest Rectangle in Histogram.
transfer steps:
  1. Compute heights of consecutive 1s for each row.
  2. Run largestRectangleArea on each row's histogram.
  3. Track the maximum rectangle area.
```

## Security note

At no point does the agent or the LLM receive `LEETCODE_SESSION` or the CSRF
token. Those are read only inside `leetmind/leetcode/client.py`. Tools return
sanitized JSON like the files in [`../samples/`](../samples/).
