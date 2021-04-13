from dataclasses import asdict

import pytest

from ..api.controllerAPI import ControllerAPI
from ..api.captionthisAPI import CaptionThis
from ..errors import ActivityError, CaptionError, VoteError
from ..utils import Section
from .base import fr_client, player, patch_redis


DEFAULT_TOTAL_PLAYERS = 5


@pytest.fixture
def empty_game() -> CaptionThis:
    return CaptionThis(
        gid="1234",
        status="0",
        max_players=str(DEFAULT_TOTAL_PLAYERS),
        total_rounds="2",
        duration="10",
        rounds_remain="2",
        current_section="0",
        current_memer_idx="0",
        current_memer="",
    )


@pytest.fixture
def full_game(empty_game):
    if not fr_client.exists("game:1234:players"):
        for i in range(DEFAULT_TOTAL_PLAYERS):
            p_id = player(i)
            fr_client.rpush("game:1234:players", p_id)
            fr_client.hset(f"game:1234:player:{p_id}", "name", f"kevin{i}")
            fr_client.hset(f"game:1234:player:{p_id}", "points", 0)
    return empty_game


@pytest.fixture
def game_at_caption(full_game: CaptionThis) -> CaptionThis:
    full_game.set_next_memer()
    full_game.start_game()
    return full_game


@pytest.fixture()
def game_new_round_with_captions(game_at_caption: CaptionThis) -> CaptionThis:
    game = game_at_caption
    game.add_meme(game.current_memer, "test_fingerprint")
    game.current_section = Section.VOTE.value
    return game


def test_create_game(empty_game):
    expected_game = {
        "gid": "1234",
        "status": "0",
        "max_players": 5,
        "total_rounds": 2,
        "duration": 10,
        "rounds_remain": 2,
        "current_section": 0,
        "current_memer_idx": 0,
        "current_memer": "",
    }
    assert asdict(empty_game) == expected_game


def test_is_playable(full_game: CaptionThis):
    assert full_game.is_playable()


def test_is_not_playable(empty_game: CaptionThis):
    assert not empty_game.is_playable()


def test_start_game(full_game: CaptionThis):
    full_game.start_game()
    expected_g = {
        "total_rounds": "2",
        "rounds_remain": "1",
        "current_section": "1",
        "current_memer_idx": "0",
        "current_memer": "",
    }
    assert fr_client.hgetall("game:1234:info") == expected_g
    assert fr_client.get("game:1234") == "1"


def test_set_next_memer(game_at_caption: CaptionThis):
    assert game_at_caption.set_next_memer()  # plr 1
    assert fr_client.hget("game:1234:info", "current_memer") == player("1")
    assert fr_client.hget("game:1234:info", "current_memer_idx") == "1"
    assert game_at_caption.set_next_memer()  # plr 2
    assert fr_client.hget("game:1234:info", "current_memer") == player("2")
    # simulate memer disconnects from the game
    fr_client.lrem("game:1234:players", 1, player("2"))
    assert game_at_caption.set_next_memer()  # plr 3
    assert fr_client.hget("game:1234:info", "current_memer") == player("3")
    assert game_at_caption.set_next_memer()  # plr 4
    assert fr_client.hget("game:1234:info", "current_memer") == player("4")
    assert not game_at_caption.set_next_memer()  # Out of index -> False
    assert game_at_caption.current_memer_idx == 0
    assert fr_client.hget("game:1234:info", "current_memer") == player("0")


def test_players(full_game: CaptionThis):
    expected_result = {}
    for i in range(DEFAULT_TOTAL_PLAYERS):
        expected_result[player(i)] = {"name": f"kevin{i}", "points": "0"}
    assert full_game.players == expected_result


def test_captions(game_at_caption: CaptionThis):
    expected_captions = {}
    for i in range(DEFAULT_TOTAL_PLAYERS):
        fr_client.hset(
            f"game:1234:player:{player(i)}:caption", "key", f"fingerprint_key{i}"
        )
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", "0")
        expected_captions[player(i)] = {"key": f"fingerprint_key{i}", "score": "0"}
    assert game_at_caption.captions == expected_captions


def test_caption(game_at_caption: CaptionThis):
    fr_client.hset(f'game:1234:player:{player("0")}:caption', "key", "fingerprint_key")
    fr_client.hset(f'game:1234:player:{player("0")}:caption', "score", "0")
    assert game_at_caption.caption == {"key": "fingerprint_key", "score": "0"}


def test_player_ready(full_game: CaptionThis):
    assert fr_client.llen("game:1234:players") == 5
    full_game.player_ready(player("0"))
    assert full_game.activity_list == [player("0")]

    # Should raises error when player ready twice
    with pytest.raises(ActivityError):
        full_game.player_ready(player("0"))

    for i in range(1, 5):
        full_game.player_ready(player(i))
    assert full_game.activity_list == [player(i) for i in range(4, -1, -1)]

    # a player disconnects after ready
    ControllerAPI.kick("1234", player("1"))
    assert player("1") not in fr_client.lrange("game:1234:activity", 0, -1)
    assert fr_client.llen("game:1234:activity") == 4


def test_player_ready_in_final(full_game: CaptionThis):
    full_game.current_section = Section.RESTART.value
    test_player_ready(full_game)


# @pytest.mark.skip
# def test_two_players_ready_simultaneously(full_game: CaptionThis):
# full_game.player_ready('ra4d0m')
# with before_after.after(
#         'services.game.captionthis.api.new_api.CaptionThis.player_ready.mon.lrange',
#         full_game.player_ready
# ):
#     full_game.player_ready('ra4d0m')
# assert fr_client.lrange("game:1234:activity", 0, -1) == ["random0", "random1"]
# assert 1 == 0
# pass


def test_all_ready(full_game: CaptionThis):
    # in WAIT section
    for i in range(DEFAULT_TOTAL_PLAYERS):
        full_game.player_ready(player(i))
    assert full_game.all_ready()


def test_all_ready_in_final(full_game: CaptionThis):
    # in FINAL section
    full_game.current_section = Section.RESTART.value
    for i in range(DEFAULT_TOTAL_PLAYERS):
        full_game.player_ready(player(i))
    assert full_game.all_ready()


def test_clear_activity_before_switch_to_next_section(full_game: CaptionThis):
    full_game.player_ready(player("0"))
    full_game.player_ready(player("1"))
    full_game.player_ready(player("2"))
    full_game.player_ready(player("3"))
    full_game.player_ready(player("4"))
    full_game.clear_activity()
    assert fr_client.exists("game:1234:activity") == 0


def test_add_meme(game_at_caption: CaptionThis):
    game = game_at_caption
    game.add_meme("ra4d0m", "fingerprint_key")
    assert (
        fr_client.hget(f"game:1234:player:{player('0')}:caption", "key")
        == "fingerprint_key"
    )

    # raises error if submit twice
    with pytest.raises(CaptionError):
        game.add_meme(player("0"), "fingerprint_key")

    # raises error if voter submit
    with pytest.raises(CaptionError):
        game.add_meme(player("1"), "fingerprint_key")

    # memer disconnects after add_meme
    ControllerAPI.kick("1234", player("0"))

    assert fr_client.hgetall(f"game:1234:player:{player('0')}:caption") == {}


def test_vote(game_new_round_with_captions: CaptionThis):
    game = game_new_round_with_captions

    # raises error if memer vote itself
    with pytest.raises(VoteError):
        game.vote(game.current_memer, 5)

    # raises error if voter votes invalid score
    with pytest.raises(VoteError):
        game.vote(player("1"), 2)

    game.vote(player("1"), 5)
    game.vote(player("2"), 10)
    assert not game.all_ready()
    game.vote(player("3"), 5)
    game.vote(player("4"), 0)
    assert fr_client.hget(f"game:1234:player:{player('0')}:caption", "score") == "20"
    assert game.all_ready()


def test_get_winner(game_new_round_with_captions: CaptionThis):
    game = game_new_round_with_captions
    # add dummy captions
    for i in range(DEFAULT_TOTAL_PLAYERS):
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "key", f"finger{i}")
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", i)
    assert game.get_winner() == [(player("4"), "finger4", "4")]
    # there are two winners
    fr_client.hset(f"game:1234:player:{player('3')}:caption", "score", 4)
    assert game.get_winner() == [
        (player("3"), "finger3", "4"),
        (player("4"), "finger4", "4"),
    ]


def test_add_point_to_winners(
    game_new_round_with_captions: CaptionThis,
):
    game = game_new_round_with_captions
    game.add_point([player("0"), player("1")])
    assert fr_client.hget(f"game:1234:player:{player('0')}", "points") == "1"
    assert fr_client.hget(f"game:1234:player:{player('1')}", "points") == "1"


def test_reset(full_game: CaptionThis):
    # Add some dummy activities
    for i in range(DEFAULT_TOTAL_PLAYERS - 2):
        fr_client.lpush("game:1234:activity", player(i))
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "key", f"finger{i}")
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", i)
        fr_client.hset(f"game:1234:player:{player(i)}", "points", 1)

    full_game.reset()
    assert fr_client.hget(f"game:1234:player:{player(i)}", "points") == "1"
    assert fr_client.exists("game:1234:activity") == 0
    for i in range(5):
        assert not fr_client.exists(f"game:1234:player:{player(i)}:caption")

    full_game.reset(new_game=True)
    for i in range(DEFAULT_TOTAL_PLAYERS - 2):
        assert fr_client.hget(f"game:1234:player:{player(i)}", "points") == "0"
