# Main handler between Redis and backend
import random
from datetime import timedelta
from collections import namedtuple
from typing import Optional, List, Union

from . import redis_client
from ..utils import generate_game_id, validate_game
from ..timers import remove_timer
from ..models import JoinRoomResult, RoomInformation, Client


class ControllerAPI:
    """Manages all transactions for game creations"""

    @staticmethod
    def create_game(
        plrs: str, rounds: str, duration: str, overrideGID: str = None
    ) -> str:
        """Create Caption-This game

        Args:
          plrs (int): Maximum amount of players
          rounds (int): Total rounds in the game
          duration (int): Duration to play in the section of caption
          overrideGID (str): Create a game with this specific game's id

        Returns:
            str: game's ID
        """
        validate_game(int(plrs), int(rounds), int(duration))

        gid = overrideGID if overrideGID else generate_game_id()
        while redis_client.get(f"game:{gid}") is not None:
            gid = generate_game_id()

        game_ns = f"game:{gid}"
        with redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.lpush("games", gid)
            # Set a 5 minutes timeout if the room is inactive.
            pipe.setex(game_ns, timedelta(minutes=5), value="0")
            pipe.hset(f"{game_ns}:info", "max_players", plrs)
            pipe.hset(f"{game_ns}:info", "total_rounds", rounds)
            pipe.hset(f"{game_ns}:info", "duration", duration)
            pipe.hset(f"{game_ns}:info", "rounds_remain", rounds)
            pipe.hset(f"{game_ns}:info", "current_section", 0)
            pipe.hset(f"{game_ns}:info", "current_memer", "")
            pipe.hset(f"{game_ns}:info", "current_memer_idx", "0")
            pipe.execute()

        return gid

    @staticmethod
    def remove_game(gid: str):
        """Remove game and any related information of it.

        Args:
          gid (str): game's id
        """
        game_ns = f"game:{gid}"
        players = redis_client.lrange(f"{game_ns}:players", 0, -1)

        with redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.lrem("games", 0, gid)
            pipe.delete(game_ns)
            pipe.delete(f"{game_ns}:info")
            pipe.delete(f"{game_ns}:activity")
            pipe.delete(f"{game_ns}:players")
            if players:
                for plr in players:
                    pipe.delete(f"{game_ns}:player:{plr}")
                    pipe.delete(f"{game_ns}:player:{plr}:caption")
            pipe.execute()

        remove_timer(gid)

    @staticmethod
    def join_game(gid: str, name: str) -> JoinRoomResult:
        """Try to join a game

        Args:
            gid (str): game's ID
            name (str): player's nickname

        Returns:
            JoinRoomResult:
        """
        game_ns = f"game:{gid}"
        game = ControllerAPI.game(gid)

        result = {
            "p_id": None,
            "g_players": None,
        }
        result.update(game)

        if redis_client.get(game_ns) == "0":
            # remove the expiration
            redis_client.persist(game_ns)

            # Add player
            p_id = str(random.getrandbits(32))
            if (players := redis_client.lrange(f"{game_ns}:players", 0, -1)) != []:
                while p_id in players:
                    p_id = str(random.getrandbits(32))

            redis_client.rpush(f"{game_ns}:players", p_id)
            redis_client.hset(f"{game_ns}:player:{p_id}", "name", name)
            redis_client.hset(f"{game_ns}:player:{p_id}", "points", 0)

            # Save one call to get game:####:players
            players.append(p_id)

            if len(players) == int(result["g_info"]["max_players"]):
                redis_client.set(game_ns, 2)

            result["p_id"] = p_id
            result["g_status"] = redis_client.get(game_ns)
            result["g_players"] = {}
            for id in players:
                result["g_players"][id] = redis_client.hgetall(f"{game_ns}:player:{id}")

        return result

    @staticmethod
    def kick(gid: str, pid: str):
        """Remove a connected player from the game

        Args:
            gid (str): game's ID
            pid (str): player's ID
        """
        game_ns = f"game:{gid}"
        redis_client.lrem(f"{game_ns}:players", 1, pid)
        redis_client.lrem(f"{game_ns}:activity", 1, pid)
        redis_client.delete(f"{game_ns}:player:{pid}")
        redis_client.delete(f"{game_ns}:player:{pid}:caption")

    @staticmethod
    def game(gid: str) -> Union[RoomInformation, dict]:
        """Retrieve game in Redis

        Args:
            gid (str): game's id

        Returns:
            Union[RoomInformation, dict]:
        """
        game_ns = f"game:{gid}"
        if redis_client.get(game_ns) is not None:
            result = {
                "g_info": redis_client.hgetall(f"{game_ns}:info"),
                "g_status": redis_client.get(game_ns),
            }
            return result
        return {}

    @staticmethod
    def games() -> List[str]:
        """Retrieve open games

        Returns:
            List: List of open game's ID.
        """
        games = redis_client.lrange("games", 0, -1)
        open_games = []
        for gid in games:
            if redis_client.get(f"game:{gid}") == "0":
                open_games.append(gid)
        return open_games

    @staticmethod
    def get_client(sid: str) -> Optional[Client]:
        """Retrieve connected client in Redis

        Args:
            sid (str): Socket.IO request's UUID

        Returns:
            Client
        """
        client = redis_client.hgetall(sid)
        return Client(**client) if client else None

    @staticmethod
    def add_client(sid: str, pid: str, gid: str):
        """Add connected client to Redis

        Args:
            sid (str): Socket.IO request's UUID
            pid (str): Connected player's ID
            gid (str): Game's ID
        """
        with redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.hset(sid, "id", pid)
            pipe.hset(sid, "gid", gid)
            pipe.execute()

    @staticmethod
    def remove_client(sid: str) -> Optional[Client]:
        """Remove connected client in Redis

        Args:
            sid (str): Socket.IO request's UUID
        """
        player = ControllerAPI.get_client(sid)
        redis_client.delete(sid)
        return player
