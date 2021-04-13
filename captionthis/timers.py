from . import celery, redis_client
from .tasks import times_up


def start_timer(gid: str, duration: str):
    """Initialize and start the timer in the background.

    Start the timer as Celery task.
    Add timer's info to redis (including task's ID)

    Args:
      gid (str): game's ID
      duration (str): timer's TTL
      section (str): Which section calls this function
    """
    task = times_up.apply_async((gid,), countdown=duration, ignore_result=True)
    # store timer's info to redis
    with redis_client.pipeline() as pipe:
        pipe.multi()
        pipe.hset(f"game:{gid}:timer", "duration", duration)
        pipe.hset(f"game:{gid}:timer", "task_id", task.id)
        pipe.execute()


def remove_timer(gid: str):
    """Cancel the celery task and call times_up directly

    Args:
        gid (str): game's ID
    """
    timer = redis_client.hgetall(f"game:{gid}:timer")
    if timer:
        celery.control.revoke(timer["task_id"])
        redis_client.delete(f"game:{gid}:timer")
