import logging
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Optional

from redis import WatchError

from . import redis_client
from ..errors import ActivityError, CaptionError, VoteError
from ..utils import Section
from ..models import Player, Caption


class PipelineWrapper:
    """Wrapper for Redis Pipelining"""

    def __init__(self):
        self.pipe = redis_client.pipeline()

    def __enter__(self):
        return self.pipe

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type:
            logging.error(f"{exc_type} - {exc_value}", exc_info=True)
        self.pipe.execute()
        # Swallow any exception coming into this context manager
        return True


class RedisMonitor(PipelineWrapper):
    """Monitor for race condition and retry"""

    def __init__(self, key):
        self.key = key
        super().__init__()

    def __enter__(self, *args, **kwargs):
        self.error_count = 0
        while True:
            try:
                self.pipe.watch(self.key)
                return super().__enter__(*args, **kwargs)
            except WatchError:
                # Retry if error
                self.error_count += 1
                logging.warning(
                    "WatchError #%d: %s; retrying", self.error_count, self.key
                )

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.pipe.unwatch()
        return super().__exit__(exc_type, exc_value, exc_traceback)


@dataclass(eq=False)
class CaptionThis:
    gid: str
    status: str
    max_players: str
    total_rounds: str
    duration: str
    rounds_remain: str
    current_section: str
    current_memer: str
    current_memer_idx: str

    def __post_init__(self):
        """__post_init__."""
        self.ns = f"game:{self.gid}"
        self.max_players: int = int(self.max_players)
        self.total_rounds: int = int(self.total_rounds)
        self.duration: int = int(self.duration)
        self.rounds_remain: int = int(self.rounds_remain)
        self.current_section: int = int(self.current_section)
        self.current_memer_idx: int = int(self.current_memer_idx)

    @property
    def players(self) -> Dict[str, Player]:
        """Get a list of connected players in this game

        Returns:
            Dict[str, Player]: Player's ID as key and its information as value.
        """
        result = {}
        for pid in redis_client.lrange(f"{self.ns}:players", 0, -1):
            result[pid] = redis_client.hgetall(f"{self.ns}:player:{pid}")
        return result

    @property
    def activity_list(self) -> List[str]:
        """Get a list of activities in the current section

        Returns:
            List[str]: A list of players' ID.
        """
        return redis_client.lrange(f"{self.ns}:activity", 0, -1)

    @property
    def captions(self) -> Dict[str, Caption]:
        """Get captions from Redis

        Returns:
            Dict[str, Caption]: A dictionary with player's ID as key and their caption as value.
        """
        results = {}
        for pid in self.players.keys():
            key = f"{self.ns}:player:{pid}:caption"
            if redis_client.exists(key):
                results[pid] = redis_client.hgetall(key)
        return results

    @property
    def caption(self) -> Optional[Caption]:
        """Get caption of the current memer.

        Returns:
            Caption:
        """
        return redis_client.hgetall(f"{self.ns}:player:{self.current_memer}:caption")

    def commit(self):
        """Update game's info to redis"""
        with PipelineWrapper() as pipe:
            pipe.set(self.ns, self.status)
            pipe.hsetnx(f"{self.ns}:info", "total_rounds", self.total_rounds)
            pipe.hset(f"{self.ns}:info", "rounds_remain", self.rounds_remain)
            pipe.hset(f"{self.ns}:info", "current_section", self.current_section)
            pipe.hset(f"{self.ns}:info", "current_memer_idx", self.current_memer_idx)
            pipe.hset(f"{self.ns}:info", "current_memer", self.current_memer)

    def start_game(self):
        """switchs section to 'caption' and begins keeping track of rounds played"""
        self.current_section = Section.CAPTION.value
        self.rounds_remain -= 1
        self.status = "1"
        self.commit()

    def set_next_memer(self) -> bool:
        """Turn next player to a memer

        Returns:
            bool: False if the current memer disconnected, True if everything is normal
        """
        current_memer = self._get_current_memer()
        state = True
        # choose next memer if current memer hasn't disconnected from the game
        if self.current_memer == current_memer:
            self.current_memer_idx += 1
            # next memer is out of index then go back to first player
            if not (self._get_current_memer()):
                self.current_memer_idx = 0
                state = False
        self.current_memer = self._get_current_memer()
        self.commit()
        return state

    def player_ready(self, pid: str):
        """Add player to activitiy list
        Args:
            pid (str): player's ID
        """
        # Only for wait and final section.
        if self.current_section in [Section.WAIT.value, Section.RESTART.value]:
            # The game must be playable.
            if len(self.players) + 1 >= 3:
                with RedisMonitor(f"{self.ns}:activity") as mon:
                    self.activity = mon.lrange(f"{self.ns}:activity", 0, -1)
                    players = self._get_players_id()
                    if pid in players and pid not in self.activity:
                        mon.lpush(f"{self.ns}:activity", pid)
                        # Avoid extra call in all_ready()
                        self.activity.append(pid)
                        return
        raise ActivityError("Invalid or duplication player's id in activity list")

    def all_ready(self) -> bool:
        """Check if every player has acted

        Returns:
            bool: Returns 'True' if all players are ready. 'False' otherwise.
        """
        players = redis_client.llen(f"{self.ns}:players")
        condition = len(self.activity)
        if self.current_section == Section.VOTE.value:
            # ignore memer
            players -= 1
        return True if condition == players else False

    def add_meme(self, pid: str, key: str):
        """Store submitted meme to Redis

        i.e: game:1234:player:pid:caption: {'key': key, 'score': 0}

        Args:
            pid (str): memer's ID
            key (str): fingerprint of the meme
        """
        if self.current_section == Section.CAPTION.value and key:
            if pid == self.current_memer:
                if not (redis_client.exists(f"{self.ns}:player:{pid}:caption")):
                    redis_client.hset(f"{self.ns}:player:{pid}:caption", "key", key)
                    redis_client.hset(f"{self.ns}:player:{pid}:caption", "score", 0)
                    return
        raise CaptionError("Invalid or duplication player's id in captions list")

    def vote(self, pid: str, score: int):
        """Vote the meme

        Args:
            pid (str): voter's ID
            score (int): score to be add by the voter
        """
        if score % 5 == 0 and 0 <= score <= 10:
            with RedisMonitor(f"{self.ns}:activity") as mon:
                if (
                    self.current_section == Section.VOTE.value
                    and pid != self.current_memer
                ):
                    self.activity = mon.lrange(f"{self.ns}:activity", 0, -1)
                    cap_key = f"{self.ns}:player:{self.current_memer}:caption"
                    cap = mon.hgetall(cap_key)
                    if pid not in self.activity and cap:
                        new_score = int(cap["score"]) + score
                        mon.hset(cap_key, "score", new_score)
                        mon.lpush(f"{self.ns}:activity", pid)
                        self.activity.append(pid)
                        return
            raise VoteError(
                "[Vote] Invalid or duplication player's id in activity list"
            )
        raise VoteError("[Vote] Invalid score")

    def add_point(self, pids: List[str]):
        """Add one point to every winner

        Args:
            pids (List[str]): winners' ID
        """
        for pid in pids:
            redis_client.hincrby(f"{self.ns}:player:{pid}", "points", 1)

    def reset(self, new_game: bool = False):
        """Clear game's state

        Args:
            new_game (bool): Flag to start a fresh game
        """
        pids = self._get_players_id()
        with PipelineWrapper() as pipe:
            for pid in pids:
                if new_game:
                    pipe.hset(f"{self.ns}:player:{pid}", "points", 0)
                pipe.delete(f"{self.ns}:player:{pid}:caption")
            pipe.delete(f"{self.ns}:activity")
        if new_game:
            self.current_section = Section.reset()
            self.current_memer = ""
            self.current_memer_idx = 0
            self.rounds_remain = self.total_rounds
        self.commit()

    def get_winner(self) -> List[Sequence[Tuple[str, str, str]]]:
        """Get winners who have the highest score in this round.

        Returns:
            List[Tuple[str, str, str]]: A list of tuples containing player's ID,
            caption's fingerprint and score
        """
        captions = self.captions
        highest_score = 0
        winners = []
        for pid, caption in captions.items():
            if (score := int(caption["score"])) > 0:
                if score > highest_score:
                    highest_score = score
                    winners = [(pid, *caption.values())]
                elif score == highest_score:
                    winners.append((pid, *caption.values()))
        return winners

    def is_playable(self) -> bool:
        """Game is playable if there are more than 3 connected players.

        Returns:
            bool: 'True' if there more than 3 connected players. 'False' otherwise.
        """
        if self.current_section != Section.WAIT.value:
            return True if redis_client.llen(f"{self.ns}:players") > 2 else False
        else:
            return True if redis_client.llen(f"{self.ns}:players") != 0 else False

    def clear_activity(self):
        """clear_activity."""
        redis_client.delete(f"{self.ns}:activity")

    def _get_players_id(self) -> List[str]:
        """Private function to get a list of connected players.

        Returns:
            List[str]: a list of connected players' ID
        """
        return redis_client.lrange(f"{self.ns}:players", 0, -1)

    def _get_current_memer(self) -> str:
        """Private function to get current memer.

        Returns:
            str: memer's ID
        """
        return redis_client.lindex(f"{self.ns}:players", self.current_memer_idx)
