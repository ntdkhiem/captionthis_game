from collections import namedtuple
from typing import Optional, TypedDict, List


class Player(TypedDict):
    name: str
    score: str


class Caption(TypedDict):
    key: str
    score: str


class GameInformation(TypedDict):
    max_players: str
    total_rounds: str
    duration: str
    rounds_remain: str
    current_section: str
    current_memer: str
    current_memer_idx: str


class RoomInformation(TypedDict):
    g_info: GameInformation
    g_status: str


class JoinRoomResult(RoomInformation):
    p_id: Optional[str]
    g_players: Optional[List[Player]]


Client = namedtuple("Client", ("id", "gid"))
