import enum
import random
from typing import Dict, List, Tuple

from .errors import (
    InvalidDuration,
    InvalidTotalPlayers,
    InvalidTotalRounds,
)


class Section(enum.IntEnum):
    """
    Enum for each section in a game
    """

    WAIT = 0
    CAPTION = 1
    VOTE = 2
    RESTART = 3

    @classmethod
    def reset(cls):
        """
        Return a default section
        """
        return cls.CAPTION.value


def validate_game(mplrs, tr, d):
    """Validate parameters for the game creation

    Args:
        mplrs (int): total players
        tr (int): total rounds
        d (int): duration

    Raises:
        InvalidTotalPlayers
        InvalidDuration
        InvalidTotalRounds
    """
    if mplrs < 3:
        raise InvalidTotalPlayers("Not enough players")
    if d < 1:
        raise InvalidDuration("Incorrect duration")
    if tr < 1:
        raise InvalidTotalRounds("Incorrect amount of rounds")


def response_formatter(data, code=200) -> Tuple[Dict, str]:
    return {
        "data": data,
    }, code


def error_formatter(data, code=200) -> Tuple[Dict, str]:
    return {
        "errors": data,
    }, code


def generate_game_id() -> str:
    """
    Generate random 4-digits number
    """
    return str(random.randint(1000, 9999))


def encode(lines: List[str]) -> str:
    # encode texts into workable filename
    encoded_lines = []

    for line in lines:
        if line:
            encoded = line
            for before, after in [
                ("_", "__"),
                ("-", "--"),
                (" ", "_"),
                ("?", "~q"),
                ("%", "~p"),
                ("#", "~h"),
                ('"', "''"),
                ("/", "~s"),
                ("\\", "~b"),
                ("\n", "~n"),
                ("&", "~a"),
            ]:
                encoded = encoded.replace(before, after)
            encoded_lines.append(encoded)
        else:
            encoded_lines.append("_")

    slug = "/".join(encoded_lines)

    return slug or "_"
