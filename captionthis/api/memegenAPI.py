import requests
import random
from collections import namedtuple
from typing import List

from ..utils import encode

Template = namedtuple(
    "Template", ["name", "key", "lines", "styles", "example", "source"]
)


def get_meme() -> Template:
    """Retrieve a random template from memegen service

    Returns:
        str: template's object
    """
    template_ids = requests.get("http://memegen:5000/templates")
    tid = random.choice(template_ids.json())
    res = requests.get(f"http://memegen:5000/templates/{tid}").json()
    return Template(**res)


def create_meme(key: str, lines: List[str], gameID: str) -> str:
    """Call Memegen to create/save the meme.

    Args:
        key (str): Template's ID
        lines (List[str]): Inputs
        gameID (str): Game's ID

    Raises:
        Exception: Request returns error

    Returns:
        str: Meme's fingerprint
    """
    slug = encode(lines)
    url = f"http://memegen:5000/images/{key}/{slug}.jpg?gameID={gameID}"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json()
    raise Exception("Request cannot be consume by Memegen service.")


def delete_game_assets(gameID: str):
    """Call Memegen to delete the folder of images of this game

    Args:
        gameID (str)
    """
    return requests.delete(f"http://memegen:5000/images/{gameID}")
