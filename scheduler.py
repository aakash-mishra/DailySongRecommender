"""
Daily scheduler using APScheduler.

Triggered via: uv run python cli.py schedule [--hour H] [--minute M]
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
            f"Daily recommendation complete: "
            f"'{result['track_name']}' by {result['artist']}"
        )
    except Exception as exc:
        log.error(f"Pipeline failed: {exc}", exc_info=True)


def start_scheduler(hour: int = 9, minute: int = 0):
    """Start the blocking daily scheduler.

    Runs _run_pipeline_sync once per day at the specified time.
    Press Ctrl+C to stop.
    """
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_pipeline_sync,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_recommendation",
        misfire_grace_time=3600,   # allow up to 1h late if machine was asleep
    )

    log.info(f"Scheduler started. Pipeline will run daily at {hour:02d}:{minute:02d}.")
    log.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Scheduler stopped.")
