"""Leetmind command-line interface.

Commands:
  leetmind sync               pull your LeetCode data into the local SQLite cache
  leetmind status             show what's cached and whether the cookie works
  leetmind analyze-solutions  build the knowledge base from your solved code (LLM)
  leetmind embed-kb            embed analyzed patterns for semantic retrieval
  leetmind kb-status          show knowledge-base contents
  leetmind ask                ask the agent a single question
  leetmind chat               interactive multi-turn chat with the agent
  leetmind search             debug: run keyword search directly (no LLM)
  leetmind patterns           debug: search the analyzed pattern KB (no agent)
  leetmind semantic-patterns  debug: semantic search the analyzed pattern KB
  leetmind bridge             debug: bridge a problem to your solved ones (LLM)
"""

from __future__ import annotations

import json

import typer

app = typer.Typer(add_completion=False, help="Leetmind - personal LeetCode AI agent.")


@app.command()
def sync(
    skip_submissions: bool = typer.Option(False, help="Only sync problems and lists."),
    code: bool = typer.Option(True, help="Fetch solution code for accepted submissions."),
    limit: int = typer.Option(0, help="Cap solved problems for submission sync (0 = all)."),
) -> None:
    """Pull problems, lists, and submissions from LeetCode into the cache."""
    from ..db.database import get_connection
    from ..leetcode.client import LeetCodeAuthError, LeetCodeClient
    from ..search.keyword_search import rebuild_index
    from ..sync.sync_lists import sync_lists
    from ..sync.sync_problems import sync_problems
    from ..sync.sync_submissions import sync_submissions

    try:
        client = LeetCodeClient()
    except LeetCodeAuthError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    conn = get_connection()
    try:
        username = client.whoami()
        if not username:
            typer.secho("Session cookie invalid or expired. Update .env.", fg=typer.colors.RED)
            raise typer.Exit(1)
        typer.secho(f"Authenticated as {username}", fg=typer.colors.GREEN)

        sync_problems(client, conn, log=typer.echo)
        sync_lists(client, conn, log=typer.echo)
        if not skip_submissions:
            sync_submissions(
                client,
                conn,
                fetch_code=code,
                limit=limit or None,
                log=typer.echo,
            )

        typer.echo("Rebuilding search index...")
        n = rebuild_index(conn)
        typer.secho(f"Indexed {n} problems. Sync complete.", fg=typer.colors.GREEN)
    finally:
        client.close()


@app.command()
def status() -> None:
    """Show cache contents and verify the session cookie (no LLM)."""
    from ..db.database import get_connection
    from ..db.repositories import MetaRepo

    conn = get_connection()
    counts = {
        "problems": conn.execute("SELECT COUNT(*) c FROM problems").fetchone()["c"],
        "solved": conn.execute("SELECT COUNT(*) c FROM problems WHERE status='ac'").fetchone()["c"],
        "lists": conn.execute("SELECT COUNT(*) c FROM lists").fetchone()["c"],
        "submissions": conn.execute("SELECT COUNT(*) c FROM submissions").fetchone()["c"],
        "indexed": conn.execute("SELECT COUNT(*) c FROM search_docs").fetchone()["c"],
    }
    meta = MetaRepo(conn)
    typer.echo("Cache contents:")
    for k, v in counts.items():
        typer.echo(f"  {k:12} {v}")
    last = meta.get("submissions_synced")
    if last is not None:
        typer.echo(f"  last submission sync count: {last}")
    if counts["problems"] == 0:
        typer.secho("Cache is empty. Run `leetmind sync` first.", fg=typer.colors.YELLOW)


@app.command(name="analyze-solutions")
def analyze_solutions_cmd(
    limit: int = typer.Option(0, help="Cap solved problems to analyze (0 = all available)."),
    force: bool = typer.Option(False, help="Re-analyze even if code is unchanged."),
) -> None:
    """Build the knowledge base from your accepted submissions (uses the LLM)."""
    _require_cache()
    from ..db.database import get_connection
    from ..kb.analyzer import analyze_solutions
    from ..kb.llm import KBConfigError

    conn = get_connection()
    try:
        stats = analyze_solutions(conn, limit=limit or None, force=force, log=typer.echo)
    except KBConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    typer.secho(
        f"Done. analyzed={stats['analyzed']} skipped={stats['skipped']} failed={stats['failed']}",
        fg=typer.colors.GREEN,
    )


@app.command(name="kb-status")
def kb_status() -> None:
    """Show knowledge-base contents (no LLM)."""
    from ..db.database import get_connection
    from ..kb.style_profile import build_style_profile

    conn = get_connection()
    analyses = conn.execute("SELECT COUNT(*) c FROM solution_analyses").fetchone()["c"]
    patterns = conn.execute("SELECT COUNT(*) c FROM pattern_docs").fetchone()["c"]
    embeddings = conn.execute("SELECT COUNT(*) c FROM solution_embeddings").fetchone()["c"]
    bridges = conn.execute("SELECT COUNT(*) c FROM problem_bridges").fetchone()["c"]
    typer.echo("Knowledge base:")
    typer.echo(f"  analyses       {analyses}")
    typer.echo(f"  indexed        {patterns}")
    typer.echo(f"  embeddings     {embeddings}")
    typer.echo(f"  cached bridges {bridges}")
    if analyses == 0:
        typer.secho("KB is empty. Run `leetmind analyze-solutions`.", fg=typer.colors.YELLOW)
        return
    profile = build_style_profile(conn)
    if profile["languages"]:
        langs = ", ".join(f"{x['language']}({x['count']})" for x in profile["languages"])
        typer.echo(f"  languages      {langs}")
    if profile["topTechniques"]:
        techs = ", ".join(x["technique"] for x in profile["topTechniques"][:8])
        typer.echo(f"  top techniques {techs}")


@app.command(name="embed-kb")
def embed_kb_cmd(
    limit: int = typer.Option(0, help="Cap analyses to embed (0 = all)."),
    force: bool = typer.Option(False, help="Re-embed even if content is unchanged."),
    batch_size: int = typer.Option(64, help="Embedding batch size."),
) -> None:
    """Embed analyzed solutions for semantic retrieval (uses embeddings API)."""
    from ..db.database import get_connection
    from ..kb.llm import KBConfigError
    from ..kb.semantic_search import embed_kb

    conn = get_connection()
    try:
        stats = embed_kb(
            conn,
            limit=limit or None,
            force=force,
            batch_size=batch_size,
            log=typer.echo,
        )
    except KBConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    typer.secho(
        f"Done. embedded={stats['embedded']} skipped={stats['skipped']} failed={stats['failed']}",
        fg=typer.colors.GREEN,
    )


_TRACE_COLORS = {
    "tool": typer.colors.CYAN,
    "result": typer.colors.BRIGHT_BLACK,
    "handoff": typer.colors.MAGENTA,
}


def _trace_emit(text: str, kind: str) -> None:
    typer.secho(text, fg=_TRACE_COLORS.get(kind))


def _make_hooks(trace: bool):
    if not trace:
        return None
    from ..agent.trace_hooks import ConsoleTraceHooks

    return ConsoleTraceHooks(emit=_trace_emit)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Your question for the agent."),
    trace: bool = typer.Option(True, "--trace/--quiet", help="Show the tool-calling trace."),
) -> None:
    """Ask the agent a single question."""
    _require_cache()
    from ..agent.agent import ask_once

    if trace:
        typer.secho(f"you: {question}", fg=typer.colors.YELLOW)
        typer.secho("orchestration:", fg=typer.colors.BRIGHT_BLACK)
    answer = ask_once(question, hooks=_make_hooks(trace))
    if trace:
        typer.secho("answer:", fg=typer.colors.BRIGHT_BLACK)
    typer.secho(answer, fg=typer.colors.GREEN)


@app.command()
def chat(
    trace: bool = typer.Option(True, "--trace/--quiet", help="Show the tool-calling trace."),
) -> None:
    """Start an interactive chat session with the agent."""
    _require_cache()
    from ..agent.agent import Conversation

    convo = Conversation(hooks=_make_hooks(trace))
    typer.secho("Leetmind chat. Type 'exit' or Ctrl-C to quit.", fg=typer.colors.CYAN)
    while True:
        try:
            message = typer.prompt("you")
        except (KeyboardInterrupt, EOFError):
            break
        if message.strip().lower() in {"exit", "quit"}:
            break
        if trace:
            typer.secho("orchestration:", fg=typer.colors.BRIGHT_BLACK)
        answer = convo.send(message)
        typer.secho(f"leetmind: {answer}", fg=typer.colors.GREEN)


@app.command()
def search(query: str = typer.Argument(...), limit: int = typer.Option(8)) -> None:
    """Debug: run the keyword search directly, bypassing the LLM."""
    from ..db.database import get_connection
    from ..search.keyword_search import search as run_search

    conn = get_connection()
    results = run_search(conn, query, limit=limit)
    out = [
        {
            "title": r.doc.get("title"),
            "id": r.doc.get("frontend_id"),
            "score": r.score,
            "matchedOn": r.reasons,
        }
        for r in results
    ]
    typer.echo(json.dumps(out, indent=2))


@app.command()
def patterns(query: str = typer.Argument(...), limit: int = typer.Option(8)) -> None:
    """Debug: search the analyzed pattern knowledge base (no agent/LLM)."""
    from ..db.database import get_connection
    from ..kb.pattern_search import search_patterns

    conn = get_connection()
    results = search_patterns(conn, query, limit=limit)
    typer.echo(json.dumps(results, indent=2))


@app.command(name="semantic-patterns")
def semantic_patterns(query: str = typer.Argument(...), limit: int = typer.Option(8)) -> None:
    """Debug: semantic search the analyzed pattern KB (uses embeddings API)."""
    from ..db.database import get_connection
    from ..kb.llm import KBConfigError
    from ..kb.semantic_search import semantic_search_patterns

    conn = get_connection()
    try:
        results = semantic_search_patterns(conn, query, limit=limit)
    except KBConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(results, indent=2))


@app.command()
def bridge(
    problem: str = typer.Argument(..., help="Problem number, slug, or title."),
    refresh: bool = typer.Option(False, help="Ignore cached bridge and recompute."),
) -> None:
    """Debug: bridge a problem to your solved ones (uses the LLM, no agent loop)."""
    _require_cache()
    from ..db.database import get_connection
    from ..kb.bridge import bridge_problem
    from ..kb.llm import KBConfigError

    conn = get_connection()
    try:
        result = bridge_problem(conn, problem, use_cache=not refresh)
    except KBConfigError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result, indent=2))


def _require_cache() -> None:
    from ..db.database import get_connection

    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) c FROM problems").fetchone()["c"]
    if count == 0:
        typer.secho("Cache is empty. Run `leetmind sync` first.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
