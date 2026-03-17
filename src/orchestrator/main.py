"""Entry point — CLI interface for the orchestrator agent.

Usage::

    python -m orchestrator run "Add login page with tests"
    python -m orchestrator status
    python -m orchestrator memory search "JWT auth"
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from orchestrator.config import ANTHROPIC_API_KEY, ENGRAM_URL, ORCHESTRATOR_MODEL, SUBAGENT_MODEL

app = typer.Typer(
    name="orchestrator",
    help="Multi-agent orchestrator — decomposes tasks and coordinates specialized AI sub-agents.",
    add_completion=False,
)
console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@app.command()
def run(
    task: str = typer.Argument(..., help="High-level task description to execute"),
    project: str = typer.Option("orchestrator", help="Engram project name for memory scoping"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Decompose only, do not execute sub-agents"),
) -> None:
    """Decompose a task and coordinate sub-agents to complete it."""
    if not ANTHROPIC_API_KEY:
        console.print("[bold red]Error:[/] ANTHROPIC_API_KEY is not set. Add it to your .env file.")
        raise typer.Exit(code=1)

    console.rule("[bold blue]Orchestrator Agent[/]")
    console.print(f"[bold]Task:[/] {task}")
    console.print(f"[bold]Project:[/] {project}")

    from orchestrator.decomposer import TaskDecomposer

    with console.status("Decomposing task…"):
        decomposer = TaskDecomposer()
        try:
            dag = decomposer.decompose(task)
        except Exception as exc:
            console.print(f"[bold red]Decomposition failed:[/] {exc}")
            raise typer.Exit(code=1)

    # Show the DAG
    table = Table(title="Task DAG", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Type", style="magenta")
    table.add_column("Depends On", style="yellow")

    for subtask in dag.subtasks:
        table.add_row(
            subtask.id,
            subtask.title,
            subtask.type.value,
            ", ".join(subtask.depends_on) or "—",
        )
    console.print(table)

    if dry_run:
        console.print("[yellow]Dry-run mode — stopping before execution.[/]")
        return

    from orchestrator.executor import DAGExecutor

    with console.status("Executing DAG…"):
        executor = DAGExecutor(project=project)
        # Attach the pre-decomposed DAG to avoid double-decomposing
        results = executor.run(dag)

    # Show results
    result_table = Table(title="Results", show_lines=True)
    result_table.add_column("Task ID", style="cyan")
    result_table.add_column("Status")
    result_table.add_column("Summary")

    for result in results:
        status_style = "green" if result.status.value == "completed" else "red"
        result_table.add_row(
            result.task_id,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            result.summary[:80] + ("…" if len(result.summary) > 80 else ""),
        )
    console.print(result_table)
    console.rule("[bold green]Done[/]")


@app.command()
def status() -> None:
    """Show current configuration and Engram connection status."""
    console.print("[bold]Configuration[/]")
    console.print(f"  Orchestrator model : {ORCHESTRATOR_MODEL}")
    console.print(f"  Sub-agent model    : {SUBAGENT_MODEL}")
    console.print(f"  Engram URL         : {ENGRAM_URL}")
    console.print(f"  API key set        : {'✅' if ANTHROPIC_API_KEY else '❌'}")

    from orchestrator.memory import EngramClient

    client = EngramClient()
    stats = client.get_stats()
    if stats:
        console.print(f"\n[bold]Engram Stats[/]: {stats}")
    else:
        console.print("\n[yellow]Engram is not reachable. Make sure it is running on port 7437.[/]")


@app.command()
def memory(
    action: str = typer.Argument(..., help="Action: 'search' or 'stats'"),
    query: Optional[str] = typer.Argument(None, help="Search query (for 'search' action)"),
) -> None:
    """Interact with Engram memory."""
    from orchestrator.memory import EngramClient

    client = EngramClient()

    if action == "stats":
        stats = client.get_stats()
        console.print(stats if stats else "Could not retrieve stats.")

    elif action == "search":
        if not query:
            console.print("[red]Please provide a search query.[/]")
            raise typer.Exit(code=1)
        results = client.search(query)
        if not results:
            console.print("No results found.")
            return
        for item in results:
            console.print(f"[cyan]{item.get('title', 'Untitled')}[/]")
            console.print(item.get("content", "")[:200])
            console.print()

    else:
        console.print(f"[red]Unknown action '{action}'. Use 'search' or 'stats'.[/]")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
