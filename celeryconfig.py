from celery.schedules import crontab


accept_content = ["json", "msgpack"]
task_serializer = "json"
task_ignore_result = True

beat_schedule = {
    "filterer-celery": {
        "task": "captionthis.tasks.filterer",
        "schedule": crontab(minute="10"),
    }
}
