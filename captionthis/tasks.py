from . import celery, redis_client


@celery.task
def times_up(gid: str, *args):
    """Celery task to execute when timer's went off

    Args:
        gid (str): game's ID
        section (str): switch to this section when done
    """
    from .wsgi_aux import app

    with app.app_context():
        from .api.captionthisAPI import CaptionThis
        from .helpers import switch_to, next_player_turn

        game_ns = f"game:{gid}"
        game_status = redis_client.get(game_ns)
        game_info = redis_client.hgetall(f"{game_ns}:info")
        game = CaptionThis(gid, game_status, **game_info)

        next_player_turn(game)
        switch_to("caption", game)
        # remove this timer from redis
        redis_client.delete(f"game:{gid}:timer")


@celery.task
def filterer():
    """This worker will filter unused games in Redis for every 10 minutes"""
    games = redis_client.lrange("games", 0, -1)
    for gid in games:
        if not redis_client.exists(f"game:{gid}"):
            redis_client.delete(f"game:{gid}:info")
            redis_client.lrem("games", 0, gid)
