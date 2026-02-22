"""
CLI entry point for DailySongRecommender.

Commands:
  recommend   Run the full pipeline (optionally dry-run)
  history     Show past recommendations
  profile     Display your Spotify taste profile
  schedule    Start the daily scheduler
"""
import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
def cli(verbose: bool):
    """DailySongRecommender — AI-powered daily music discovery."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Find a recommendation but skip the email and history log.",
)
def recommend(dry_run: bool):
    """Run the full recommendation pipeline."""
    from agents.orchestrator import run_pipeline

    if dry_run:
        rprint("[yellow]Dry-run mode: Claude will run but no email will be sent "
               "and nothing will be saved to history.[/yellow]")

    try:
        with console.status("[bold green]Running pipeline…"):
            result = asyncio.run(run_pipeline(dry_run=dry_run))
    except Exception as exc:
        rprint(f"[bold red]Pipeline failed:[/bold red] {exc}")
        sys.exit(1)

    rprint(f"\n[bold green]Recommendation[/bold green]")
    rprint(f"  [bold]{result['track_name']}[/bold] by {result['artist']}")
    rprint(f"  Genre territory : {result['genre']}")
    rprint(f"  Spotify link    : {result['spotify_url']}")
    rprint(f"\n[italic]{result['explanation']}[/italic]")

    if dry_run:
        rprint("\n[yellow](dry-run: no email sent, not saved to history)[/yellow]")
    else:
        rprint("\n[green]Email sent and logged to history.[/green]")


@cli.command()
@click.option("--limit", "-n", default=10, show_default=True,
              help="Number of past recommendations to show.")
def history(limit: int):
    """Show past song recommendations."""
    from core.database import init_db, get_history

    init_db()
    rows = get_history(limit=limit)

    if not rows:
        rprint("[yellow]No recommendations yet. Run [bold]recommend[/bold] first.[/yellow]")
        return

    table = Table(title=f"Last {len(rows)} Recommendations", show_lines=False)
    table.add_column("Date", style="dim", no_wrap=True)
    table.add_column("Song", style="bold")
    table.add_column("Artist")
    table.add_column("Genre", style="cyan")

    for row in rows:
        table.add_row(
            row["recommended_at"][:10],
            row["track_name"],
            row["artist"],
            row.get("genre") or "",
        )

    console.print(table)


@cli.command()
@click.option("--max-songs", default=500, show_default=True,
              help="Max liked songs to fetch when building the profile.")
def profile(max_songs: int):
    """Display your current Spotify music taste profile."""
    from agents.profiler import build_profile

    with console.status("[bold green]Fetching your profile from Spotify…"):
        p = asyncio.run(build_profile(max_liked_songs=max_songs))

    rprint(f"\n[bold]Liked songs in library :[/bold] {p['liked_song_count']}")
    rprint(f"[bold]Fetched for analysis   :[/bold] {len(p['liked_song_ids'])}")
    rprint(f"\n[bold]Comfort zone genres (top 5):[/bold]")
    for g in p["comfort_zone_genres"]:
        count = p["genre_distribution"].get(g, 0)
        rprint(f"  {g}  ({count} artists)")

    rprint(f"\n[bold]Full top-genre ranking:[/bold]")
    for i, g in enumerate(p["top_genres"], 1):
        count = p["genre_distribution"].get(g, 0)
        rprint(f"  {i:2}. {g}  ({count})")

    rprint(f"\n[bold]Average audio features:[/bold]")
    for k, v in p["avg_audio_features"].items():
        bar = "█" * int(v * 20) if k not in ("loudness", "tempo") else ""
        rprint(f"  {k:<22} {v:>7.3f}  {bar}")


@cli.command()
@click.option("--hour", default=9, show_default=True,
              help="Hour to run the recommendation (24h format).")
@click.option("--minute", default=0, show_default=True,
              help="Minute past the hour to run.")
def schedule(hour: int, minute: int):
    """Start the APScheduler daily recommendation scheduler."""
    from scheduler import start_scheduler
    start_scheduler(hour=hour, minute=minute)


if __name__ == "__main__":
    cli()
