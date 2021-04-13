from functools import wraps
from typing import Callable, Union

from flask import current_app, request

from . import socketio
from .api.controllerAPI import ControllerAPI
from .api.memegenAPI import get_meme
from .api.captionthisAPI import CaptionThis
from .errors import CaptionThisError
from .timers import remove_timer, start_timer
from .utils import Section


def ingame_only(f):
    """Wrapper function to restrict foreign accesses.

    Only allow the function to execute when session's ID
    is registered and the player is in the game
    """

    @wraps(f)
    def wrapped(self, *args, **kwargs) -> Union[bool, Callable]:
        client = ControllerAPI.get_client(request.sid)
        if client:
            game = ControllerAPI.game(client.gid)
            if not game:
                return False
        else:
            current_app.logger.warning(
                "Foreign request id attempted to communicate with socket.io"
            )
            return False
        game = CaptionThis(client.gid, game["g_status"], **game["g_info"])
        try:
            return f(self, *args, **kwargs, player=client, game=game)
        except CaptionThisError as e:
            socketio.emit("gameException", e.msg, room=request.sid, namespace="/game")

    return wrapped


def switch_to(sect: str, game: CaptionThis):
    game.clear_activity()
    socketio.sleep(current_app.config["TIME_DELAY"])
    if sect == "caption":
        game.current_section = Section.CAPTION.value
        template = get_meme()

        remove_timer(game.gid)
        socketio.emit("gameTimeUp", room=game.gid, namespace="/game")

        socketio.emit(
            "gameStart",
            {
                "template": template._asdict(),
                "memer": game.current_memer,
                "total_rounds": game.total_rounds,
                "rounds_remain": game.rounds_remain,
            },
            room=game.gid,
            namespace="/game",
        )

        start_timer(game.gid, game.duration)
        socketio.emit("gameTimeStart", game.duration, room=game.gid, namespace="/game")
    elif sect == "vote":
        game.current_section = Section.VOTE.value

        remove_timer(game.gid)
        socketio.emit("gameTimeUp", room=game.gid, namespace="/game")

        socketio.emit("gameSwitchPage", "vote", room=game.gid, namespace="/game")
        socketio.emit("gameGetCaption", game.caption, room=game.gid, namespace="/game")

        start_timer(game.gid, current_app.config["DEFAULT_VOTE_DURATION"])
        socketio.emit(
            "gameTimeStart",
            current_app.config["DEFAULT_VOTE_DURATION"],
            room=game.gid,
            namespace="/game",
        )
    game.commit()


def next_player_turn(game: CaptionThis) -> bool:
    """Choose next memer

    Args:
        game (CaptionThis): game's instance

    Returns:
        bool: False if this is the end, True otherwise
    """
    if not game.set_next_memer():
        winners = game.get_winner()
        game.add_point([item[0] for item in winners])
        socketio.emit("gameGetWinner", winners, room=game.gid, namespace="/game")
        if game.rounds_remain == 0:
            # this is the last round in the game
            socketio.emit("gameEnd", game.players, room=game.gid, namespace="/game")
            game.current_section = Section.RESTART.value
            game.commit()
            # to avoid duplication in the list
            game.clear_activity()
            # remove timer here since the game will not call switch_to in event.
            remove_timer(game.gid)
            socketio.emit("gameTimeUp", room=game.gid, namespace="/game")
            return False
        game.reset()
        game.start_game()
    return True
