"""
Daily scheduler using APScheduler.

Runs the recommendation pipeline at specified times each day.
Triggered via: uv run python cli.py schedule
"""
import asyncio
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

log = logging.getLogger(__name__)


def _run_pipeline_sync():
    """Synchronous wrapper so APScheduler can call the async pipeline."""
    from agents.orchestrator import run_pipeline
    try:
        result = asyncio.run(run_pipeline(dry_run=False))
        log.info(
            f"Recommendation complete: "
            f"'{result['track_name']}' by {result['artist']}"
        )
    except Exception as exc:
        log.error(f"Pipeline failed: {exc}", exc_info=True)


def start_scheduler(schedule_times: list[tuple[int, int]] = None):
    """Start the blocking daily scheduler.

    Runs the pipeline at specified times each day.

    Args:
        schedule_times: List of (hour, minute) tuples in 24h format.
                       Defaults to [(9, 0), (17, 0)] for 9 AM and 5 PM.

    Press Ctrl+C to stop.
    """
    if schedule_times is None:
        # Default: 9 AM EST and 5 PM EST
        schedule_times = [(9, 0), (17, 0)]

    scheduler = BlockingScheduler()

    for idx, (hour, minute) in enumerate(schedule_times):
        scheduler.add_job(
            _run_pipeline_sync,
            trigger="cron",
            hour=hour,
            minute=minute,
            id=f"recommendation_{idx}",
            misfire_grace_time=3600,   # allow up to 1h late if machine was asleep
        )
        log.info(f"  • Daily at {hour:02d}:{minute:02d}")

    log.info(f"Scheduler started with {len(schedule_times)} daily job(s).")
    log.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Scheduler stopped.")
