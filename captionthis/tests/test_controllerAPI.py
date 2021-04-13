import time
from datetime import timedelta

import pytest
from pytest_mock.plugin import MockerFixture

from ..api.controllerAPI import ControllerAPI, Client
from ..errors import (
    InvalidDuration,
    InvalidTotalRounds,
    InvalidTotalPlayers,
)

from .base import fr_client, patch_redis


@pytest.fixture
def id_empty_game():
    return ControllerAPI.create_game("5", "2", "10", "1234")


def test_create_game_with_invalidTotalPlayers():
    invalidTotalPlayers = 2
    with pytest.raises(InvalidTotalPlayers):
        ControllerAPI.create_game(invalidTotalPlayers, "2", "10")


def test_create_game_with_invalidTotalRounds():
    invalidTotalRounds = 0
    with pytest.raises(InvalidTotalRounds):
        ControllerAPI.create_game("5", invalidTotalRounds, "10")


def test_create_game_with_invalidDuration():
    invalidDuration = 0
    with pytest.raises(InvalidDuration):
        ControllerAPI.create_game("5", "2", invalidDuration)


def test_create_game_duplicate_id(id_empty_game):
    gid = ControllerAPI.create_game("5", "2", "10", "1234")
    assert gid != "1234"


def test_create_valid_game():
    ControllerAPI.create_game("5", "2", "10", "1234")
    assert fr_client.lrange("games", 0, -1) == ["1234"]
    assert fr_client.get("game:1234") == "0"
    assert fr_client.ttl("game:1234") == timedelta(minutes=5).seconds
    g = ControllerAPI.game("1234")
    expected_g = {
        "g_status": "0",
        "g_info": {
            "max_players": "5",
            "total_rounds": "2",
            "duration": "10",
            "rounds_remain": "2",
            "current_section": "0",
            "current_memer_idx": "0",
            "current_memer": "",
        },
    }
    assert g == expected_g


def test_player_join_game(id_empty_game, mocker: MockerFixture):
    mocker.patch(
        "captionthis.api.controllerAPI.random.getrandbits",
        return_value="ra4d0m",
    )
    res = ControllerAPI.join_game(id_empty_game, "kevin0")
    expected_res = {
        "p_id": "ra4d0m",
        "g_players": {"ra4d0m": {"name": "kevin0", "points": "0"}},
        "g_info": {
            "max_players": "5",
            "total_rounds": "2",
            "duration": "10",
            "rounds_remain": "2",
            "current_section": "0",
            "current_memer_idx": "0",
            "current_memer": "",
        },
        "g_status": "0",
    }
    assert res == expected_res
    plrs = fr_client.lrange("game:1234:players", 0, -1)
    assert plrs == ["ra4d0m"]
    plr = fr_client.hgetall("game:1234:player:ra4d0m")
    assert plr == {"name": "kevin0", "points": "0"}
    assert fr_client.ttl("game:1234") == -1


def test_duplicate_players(id_empty_game, mocker: MockerFixture):
    mocker.patch(
        "captionthis.api.controllerAPI.random.getrandbits",
        side_effect=["ra4d0m", "ra4d0m", "ra4d1m"],
    )
    # if pid is already exist in the game, the api should find a new id.
    res1 = ControllerAPI.join_game(id_empty_game, "kevin0")
    res2 = ControllerAPI.join_game(id_empty_game, "kevin1")
    assert res1["p_id"] != res2["p_id"]


@pytest.mark.slow
def test_join_expired_game(mocker: MockerFixture):
    mocker.patch("captionthis.api.controllerAPI.timedelta", return_value=5)
    ControllerAPI.create_game("5", "2", "10", "1234")
    time.sleep(5)
    res = ControllerAPI.join_game("1234", "kevin0")
    assert res["p_id"] is None
    assert res["g_players"] is None


def test_game_reaches_max(id_empty_game):
    """When enough players joined the game, the status should be 2"""
    for i in range(5):
        ControllerAPI.join_game("1234", f"kevin{i}")
    assert fr_client.get("game:1234") == "2"
    # next player can't join this game
    res = ControllerAPI.join_game("1234", "kevin5")
    assert res["p_id"] is None
    assert res["g_players"] is None


def test_kick_player(id_empty_game, mocker: MockerFixture):
    for i in range(5):
        mocker.patch(
            "captionthis.api.controllerAPI.random.getrandbits",
            return_value=f"r{i}",
        )
        ControllerAPI.join_game("1234", f"kevin{i}")
    ControllerAPI.kick("1234", "r0")
    assert len(fr_client.lrange("game:1234:players", 0, -1)) == 4
    assert fr_client.get("game:1234:player:r0") is None
    # just to make sure that the API didn't affect others as well.
    assert fr_client.hgetall("game:1234:player:r1") is not None


def test_remove_empty_game(id_empty_game):
    ControllerAPI.remove_game("1234")
    assert fr_client.get("game:1234") is None
    assert fr_client.get("game:1234:info") is None
    assert fr_client.lrange("games", 0, -1) == []


def test_remove_playing_game(id_empty_game, mocker: MockerFixture):
    for i in range(5):
        mocker.patch(
            "captionthis.api.controllerAPI.random.getrandbits",
            return_value=f"ra4d{i}m",
        )
        ControllerAPI.join_game("1234", f"kevin{i}")
    ControllerAPI.remove_game("1234")
    assert fr_client.lrange("games", 0, -1) == []
    assert fr_client.get("game:1234") is None
    assert fr_client.get("game:1234:info") is None
    assert fr_client.get("game:1234:players") is None
    for i in range(5):
        assert fr_client.get(f"game:1234:player:ra4d{i}m") is None


def test_add_client():
    ControllerAPI.add_client("r1", "12ieu", "1234")
    expected_client = {"id": "12ieu", "gid": "1234"}
    assert fr_client.hgetall("r1") == expected_client


def test_get_client():
    fr_client.hset("r1", "id", "12ieu")
    fr_client.hset("r1", "gid", "1234")
    expected_client = Client(id="12ieu", gid="1234")
    assert ControllerAPI.get_client("r1") == expected_client


def test_remove_client():
    fr_client.hset("r1", "id", "12ieu")
    fr_client.hset("r1", "gid", "1234")
    ControllerAPI.remove_client("r1")
    assert fr_client.hgetall("r1") == {}
