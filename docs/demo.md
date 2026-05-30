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

## Security note

At no point does the agent or the LLM receive `LEETCODE_SESSION` or the CSRF
token. Those are read only inside `leetmind/leetcode/client.py`. Tools return
sanitized JSON like the files in [`../samples/`](../samples/).
