import logging

from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task
def test_celery_task(name: str = "World") -> str:
    """A working test task to verify Celery execution."""
    logger.info("Executing test_celery_task for name: %s", name)
    greeting = f"Hello, {name}! Celery is working."
    logger.info("Task completed successfully: %s", greeting)
    return greeting
