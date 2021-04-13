import enum
from typing import Any, Tuple, List, Dict, Union
from unittest import mock

import pprint

# for typing purposes
from flask_socketio.test_client import SocketIOTestClient

from .. import socketio
from ..api.controllerAPI import ControllerAPI
from ..api.captionthisAPI import CaptionThis
from ..models import Player
from ..utils import Section
from .base import player, app, fr_client


class Default(enum.IntEnum):
    TOTAL_PLAYERS = 5
    TOTAL_ROUNDS = 2
    DURATION = 10


class NewGame:
    def __init__(
        self,
        section="wait",
        filled=False,
        total_players=Default.TOTAL_PLAYERS.value,
        total_rounds=Default.TOTAL_ROUNDS.value,
        duration=Default.DURATION.value,
    ):
        self.section = section
        self.filled = filled
        self.total_players = total_players
        self.total_rounds = total_rounds
        self.duration = duration

    def __enter__(self):
        self.gid = ControllerAPI.create_game(
            str(self.total_players), str(self.total_rounds), str(self.duration), "1234"
        )
        info = ControllerAPI.game(self.gid)
        self.game = CaptionThis(self.gid, info["g_status"], **info["g_info"])

        if self.filled:
            self.clients = []
            for i in range(self.total_players):
                with mock.patch(
                    "captionthis.api.controllerAPI.random.getrandbits",
                    return_value=player(i),
                ):
                    self.clients.append(init_client(self.gid, f"kevin{i}"))

        # get player's unique id in the game
        self.clients_id = sorted(fr_client.lrange("game:1234:players", 0, -1))

        if self.section == "restart":
            fr_client.hset("game:1234:info", "current_section", "3")
            self.game.current_section = Section.RESTART.value
            return self

        if self.section == "wait":
            return self

        self.game.start_game()
        self.game.set_next_memer()

        if self.section == "caption":
            return self

        # Add a caption for the first player (memer)
        fr_client.hset(
            f'game:1234:player:{player("0")}:caption', "key", "test_fingerprint"
        )
        fr_client.hset(f'game:1234:player:{player("0")}:caption', "score", "0")
        fr_client.hset("game:1234:info", "current_section", "2")
        self.game.current_section = Section.VOTE.value

        if self.section == "vote":
            return self

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        ControllerAPI.remove_game(self.gid)


class MessageBuilder:
    @staticmethod
    def gameConnected(
        pid: str, d_plrs: Dict[str, Player], tr: int
    ) -> Tuple[str, List[List[Union[str, Dict[str, Player], str]]]]:
        return ("gameConnected", [[pid, d_plrs, str(tr)]])

    @staticmethod
    def gamePlayerConnected(
        pid: str, name: str, points: str
    ) -> Tuple[str, List[Dict[str, Player]]]:
        return ("gamePlayerConnected", [MessageBuilder._player(pid, name, points)])

    @staticmethod
    def gameStart(**kwargs) -> Tuple[str, List[Dict[str, Any]]]:
        expected_gameStart = {
            "template": {
                "name": "Ancient Aliens Guy",
                "key": "aag",
                "lines": "2",
                "styles": [],
                "example": "http://dummy_url_from_memegen",
                "source": "http://knowyourmeme.com/memes/ancient-aliens",
            },
            "total_rounds": Default.TOTAL_ROUNDS.value,
        }
        expected_gameStart.update(kwargs)
        return ("gameStart", [expected_gameStart])

    @staticmethod
    def gameGetCaption(key: str) -> Tuple[str, List[Dict[str, str]]]:
        return ("gameGetCaption", [{"key": key, "score": "0"}])

    @staticmethod
    def gameGetScore(score: int) -> Tuple[str, List[Dict[str, str]]]:
        return ("gameGetScore", [str(score)])

    @staticmethod
    def default_msg(flag: str, value: str = None) -> Tuple[str, List[str]]:
        return (flag, [value]) if value else (flag, [])

    @staticmethod
    def _player(pid: str, name: str, points: str) -> Dict[str, Player]:
        return {pid: {"name": name, "points": points}}


def _pprint(client):
    pprint.pprint(client.get_received(namespace="/game"), sort_dicts=False)


def validate_socketio_msg(clients, validators):
    """Validate expected messages in each client's list of received messages

    Args:
      clients (List[SocketIOTestClient]): A list of connected clients
      validators (List[msg_name, msg_value]): expected messages to compare
    """
    if clients and type(clients) == list:
        for client in clients:
            msg = client.get_received(namespace="/game")
            for msg_name, msg_data in validators:
                _validate_msg(msg, msg_name, msg_data)
                # Remove the msg after success validation
                msg_index = -1
                for i, m in enumerate(msg):
                    if m["name"] == msg_name:
                        msg_index = i
                        break
                del msg[msg_index]
    else:
        raise Exception("Received empty list of clients")


def _validate_msg(msgl, name, data) -> bool:
    """Validate the expected message is in the list of received messages

    Args:
      msgl (List[*SocketIOMessage]): List of received messages
      name (str): Expected message's name
      data (value or values): Expected message's value

    Raises:
      Exception: Raises error when the expected msg DNE.

    Returns:
      bool: True if there is expected message in the list
    """
    msg = []
    for m in msgl:
        if m["name"] == name:
            msg.append(m)

    if not msg:
        raise Exception(f"Cannot find the message {name} in the list")

    try:
        if len(msg) == 1:
            msg = msg[0]
            # if 'data' is singular
            if len(data) == 1 and data[0] is not tuple:
                assert msg["args"][0] == data[0]
            else:
                for item in data:
                    assert msg["args"][0].get(item[0]) == item[1]

        else:
            # to avoid raising error the first message I check
            # find the desired message among received messages
            for m in msg:
                if len(data) == 1 and data[0] is not tuple:
                    if m["args"][0] == data[0]:
                        return True
                    else:
                        for item in data:
                            if m["args"][0].get(item[0]) == item[1]:
                                return True
    except Exception as e:
        raise Exception(f"Validator exception: {e}")


def init_client(gid: str, n: str) -> SocketIOTestClient:
    """Initialize a socketIO session

    Args:
      gid (str): game's id
      n (str): player's name

    Returns:
      SocketIOTestClient: SocketIO session
    """
    return socketio.test_client(
        app,
        namespace="/game",
        query_string=f"id={gid}&name={n}",
        flask_test_client=app.test_client(),
    )
