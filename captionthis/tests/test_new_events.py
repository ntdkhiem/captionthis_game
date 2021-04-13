import random

from pytest_mock import MockerFixture

from .. import socketio
from ..utils import Section
from ..api.controllerAPI import ControllerAPI
from .base import app, fr_client, mocked_requests_get, patch_redis
from .helpers import NewGame, validate_socketio_msg, init_client, player, _pprint
from .helpers import MessageBuilder as M


def test_connect_to_server(mocker: MockerFixture):
    with NewGame() as g:
        mocker.patch(
            "captionthis.api.controllerAPI.random.getrandbits",
            return_value="r8nd0m1D",
        )
        # valid connection (with queryString)
        client = socketio.test_client(
            app,
            namespace="/game",
            query_string=f"id={g.gid}&name=kevin",
            flask_test_client=app.test_client(),
        )
        assert client.is_connected(namespace="/game")
        validate_socketio_msg(
            [client],
            [
                M.gameConnected(
                    "r8nd0m1D", M._player("r8nd0m1D", "kevin", "0"), g.total_rounds
                ),
                M.gamePlayerConnected("r8nd0m1D", "kevin", "0"),
            ],
        )


################################  WAIT SECTION ################################
def test_join_game(mocker: MockerFixture):
    # Best case scenario
    # All players connected successfully
    with NewGame() as g:
        clients = []
        lst_expected_msg = []
        for i in range(g.total_players):
            preID = f"Rand0m{i}"
            mocker.patch(
                "captionthis.api.controllerAPI.random.getrandbits",
                return_value=preID,
            )
            clients.append(init_client(g.gid, f"kevin{i}"))
            lst_expected_msg.append(
                M.gamePlayerConnected(f"Rand0m{i}", f"kevin{i}", "0")
            )
        # the first player should receive all gamePlayerConnect
        validate_socketio_msg([clients[0]], [*lst_expected_msg, ("gameReady", [])])


def test_join_non_existence_game():
    client = init_client("3475", "kevin")
    assert not client.is_connected(namespace="/game")


def test_player_join_full_game():
    with NewGame(filled=True) as g:
        client = init_client(g.gid, "irregularBot")
        assert client.is_connected(namespace="/game") is False


def test_wait_section_scenario_1():
    # Senario #1
    # A first player who connected to the game disconnects.
    # The game server should remove this newly created game.
    with NewGame() as g:
        client = init_client(g.gid, "kevin1")
        client.disconnect(namespace="/game")
        # assert 1 == 0
        assert not client.is_connected(namespace="/game")
        assert not ControllerAPI.game(g.gid)


def test_wait_section_scenario_2():
    # Senario #2
    # There is 2 players in the wait section
    # one player disconnects, the game should not be remove
    # A player would like to connect should be allow to do so
    with NewGame() as g:
        client1 = init_client(g.gid, "kevin1")
        init_client(g.gid, "kevin2")
        client1.disconnect(namespace="/game")
        # 'True' if there is data, 'False' if the returned result is {}
        assert bool(ControllerAPI.game(g.gid))
        client3 = init_client(g.gid, "kevin3")
        assert client3.is_connected(namespace="/game")


def test_wait_play_on_gameReady(mocker: MockerFixture):
    # if playable amount of players (3 or more) click 'ready'
    # the game server should proceed to caption section and
    # all players should receive a gameStart msg
    with NewGame() as g:
        clients = []
        for i in range(random.randint(3, g.total_players)):
            mocker.patch(
                "captionthis.api.controllerAPI.random.getrandbits",
                return_value=player(i),
            )
            clients.append(init_client(g.gid, f"kevin{i}"))
        for client in clients:
            client.emit("playerReady", namespace="/game")
        validate_socketio_msg(
            clients,
            [
                M.gameStart(memer=player("0"), rounds_remain=g.total_rounds - 1),
                ("gameTimeStart", [g.duration]),
            ],
        )


def test_wait_section_scenario_3(mocker: MockerFixture):
    # Senario #3
    # 3 players clicked 'ready', one disconnects, one hasn't click yet
    # the game server will remove disconnected player and should proceed
    # to caption section when the last player clicks 'ready'
    mocked_requests = mocker.patch(
        "captionthis.api.memegenAPI.requests.get",
        side_effect=mocked_requests_get,
    )
    with NewGame() as g:
        clients = []
        for i in range(5):
            mocker.patch(
                "captionthis.api.controllerAPI.random.getrandbits",
                return_value=player(i),
            )
            clients.append(init_client(g.gid, f"kevin{i}"))

        clients[0].emit("playerReady", namespace="/game")
        clients[1].emit("playerReady", namespace="/game")
        clients[2].emit("playerReady", namespace="/game")
        clients[3].disconnect(namespace="/game")
        assert fr_client.get("game:1234") == "0"
        clients[4].emit("playerReady", namespace="/game")

        validate_socketio_msg(
            [clients[0], clients[1], clients[2], clients[4]],
            [
                M.gameStart(memer=player("0"), rounds_remain=g.total_rounds - 1),
                M.default_msg("gameTimeStart", g.duration),
                M.default_msg("gamePlayerDisconnected", player("3")),
                M.default_msg("gameOpen"),
                M.default_msg("gameFull"),
            ],
        )
        assert len(mocked_requests.call_args_list) == 2
        assert fr_client.get("game:1234") == "1"


def test_wait_section_scenario_4():
    # Senario #4
    # all players but one clicked 'ready', last player disconnects
    # the game server should proceed to caption section
    with NewGame(filled=True) as g:
        for client in g.clients[:-1]:
            client.emit("playerReady", namespace="/game")
        g.clients[-1].disconnect(namespace="/game")
        g.clients.pop()
        validate_socketio_msg(
            g.clients,
            [
                M.gameStart(memer=player("0"), rounds_remain=g.total_rounds - 1),
                M.default_msg("gameTimeStart", g.duration),
            ],
        )


def test_wait_section_player_ready_game_not_playable():
    # A player clicks 'ready' when the game isn't playable
    # the server should send a gameException msg
    with NewGame() as g:
        client = init_client(g.gid, "kevin1")
        client.emit("playerReady", namespace="/game")
        msg = client.get_received(namespace="/game")
        assert msg[-1]["name"] == "gameException"


################################################################


################################  CAPTION SECTION ################################
def test_c_memer_submits_caption():
    # Best scenario
    # memer submits his caption
    # the server should proceed to vote section
    # all players should receive gameSwitchPage and gameGetCaption
    with NewGame(filled=True) as g:
        # Simulate all players ready to start the game + timer
        for c in g.clients:
            c.emit("playerReady", room=g.gid, namespace="/game")

        g.clients[0].emit(
            "captionSubmit",
            {"key": "aag", "lines": ["hello world", "this is test"]},
            namespace="/game",
        )

        validate_socketio_msg(
            g.clients,
            [
                M.default_msg("gameTimeStart", g.duration),
                M.default_msg("gameSwitchPage", "vote"),
                M.default_msg("gameTimeUp"),
                M.default_msg("gameTimeStart", app.config["DEFAULT_VOTE_DURATION"]),
                M.gameGetCaption("test_fingerprint"),
            ],
        )


def test_memer_submits_twice_should_raise_error():
    with NewGame(section="caption", filled=True, total_players=3) as g:
        # Raises error when memer submits twice
        g.clients[0].emit(
            "captionSubmit",
            {"key": "aag", "lines": ["hello world", "this is test"]},
            namespace="/game",
        )
        g.clients[0].emit(
            "captionSubmit",
            {"key": "aag", "lines": ["hello world", "this is test"]},
            namespace="/game",
        )
        validate_socketio_msg(
            [g.clients[0]],
            [
                M.default_msg(
                    "gameException",
                    "Invalid or duplication player's id in captions list",
                )
            ],
        )
        # Others shouldn't receive gameException
        for client in g.clients[1:]:
            msg = client.get_received(namespace="/game")
            for m in msg:
                assert m["name"] != "gameException"


def test_c_memer_disconnects():
    # The game should proceed to pick the next memer
    with NewGame(section="caption", filled=True) as g:
        g.clients[0].disconnect(namespace="/game")

        validate_socketio_msg(
            g.clients[1:],
            [
                M.default_msg("gamePlayerDisconnected", g.clients_id[0]),
                M.gameStart(memer=player("1"), rounds_remain=g.total_rounds - 1),
                M.default_msg("gameReason", "Memer disconnected"),
            ],
        )


def test_c_voters_disconnect():
    with NewGame(section="caption", filled=True) as g:
        g.clients[1].disconnect(namespace="/game")
        g.clients[2].disconnect(namespace="/game")

        validate_socketio_msg(
            [g.clients[0], g.clients[3], g.clients[4]],
            [
                M.default_msg("gamePlayerDisconnected", g.clients_id[1]),
                M.default_msg("gamePlayerDisconnected", g.clients_id[2]),
            ],
        )
        # Doesn't change anything
        assert ControllerAPI.game(g.gid)

        # Game no longer playable
        g.clients[4].disconnect(namespace="/game")

        validate_socketio_msg(
            [g.clients[0], g.clients[3]],
            [
                M.default_msg("gamePlayerDisconnected", g.clients_id[4]),
                M.default_msg("gameDisconnected"),
            ],
        )
        assert not ControllerAPI.game(g.gid)


################################################################


################################  VOTE SECTION ################################
def test_v_scenario_1():
    # Best case scenario
    # all voters except memer vote
    with NewGame(section="vote", filled=True) as g:
        total_points = 0
        validators = []
        for i, client in enumerate(g.clients[1:]):
            score = random.choice([0, 5, 10])
            client.emit("voteSubmit", score, namespace="/game")
            total_points += score
            validators.append(M.default_msg("gamePlayerReady", g.clients_id[i + 1]))

        validators += [
            M.gameGetScore(score=total_points),
            M.gameStart(memer=player("1"), rounds_remain=g.total_rounds - 1),
        ]
        validate_socketio_msg(g.clients, validators)
        assert fr_client.hget("game:1234:info", "current_section") == "1"


def test_v_scenario_2():
    # Current memer is the last memer in the round
    with NewGame(section="vote", filled=True) as g:
        for i in range(len(g.clients[:-1])):
            score = 5
            # give first player highest score
            if i == 0:
                score = 10
            fr_client.hset(
                f"game:1234:player:{player(i)}:caption", "key", f"test_fingerprint{i}"
            )
            fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", score)
            assert g.game.set_next_memer()

        # simulate last player (memer) submits their caption
        i += 1
        fr_client.hset(
            f"game:1234:player:{player(i)}:caption", "key", f"test_fingerprint{i}"
        )
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", "0")

        # simulate voters voting the meme
        validators = []
        for i, client in enumerate(g.clients[:-1]):
            client.emit("voteSubmit", 0, namespace="/game")
            validators.append(M.default_msg("gamePlayerReady", g.clients_id[i]))

        validators += [
            M.gameGetScore(score=0),
            M.gameStart(memer=player("0"), rounds_remain=g.total_rounds - 2),
            M.default_msg("gameGetWinner", [[player("0"), "test_fingerprint0", "10"]]),
        ]
        validate_socketio_msg(g.clients, validators)
        assert fr_client.hget("game:1234:info", "current_section") == "1"
        assert fr_client.hget(f'game:1234:player:{player("0")}', "points") == "1"
        assert not fr_client.exists("game:1234:activity")
        for pid in g.clients_id:
            assert not fr_client.exists(f"game:1234:player:{pid}:caption")


def test_v_memer_scenario_3():
    # this is the last memer in the last round in the game
    with NewGame(section="vote", filled=True) as g:
        g.game.rounds_remain = 0
        for i in range(len(g.clients[:-1])):
            score = 5
            # give first player highest score
            if i == 0:
                score = 10
            fr_client.hset(
                f"game:1234:player:{player(i)}:caption", "key", f"test_fingerprint{i}"
            )
            fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", score)
            assert g.game.set_next_memer()

        i += 1
        fr_client.hset(
            f"game:1234:player:{player(i)}:caption", "key", f"test_fingerprint{i}"
        )
        fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", "0")

        validators = []
        for i, client in enumerate(g.clients[:-1]):
            client.emit("voteSubmit", 0, namespace="/game")
            validators.append(M.default_msg("gamePlayerReady", g.clients_id[i]))

        expected_gameEnd = {}
        expected_gameEnd[g.clients_id[0]] = {"name": f"kevin0", "points": "1"}
        for i in range(1, len(g.clients_id)):
            expected_gameEnd[g.clients_id[i]] = {"name": f"kevin{i}", "points": "0"}
        validators += [
            M.gameGetScore(score=0),
            M.default_msg("gameEnd", expected_gameEnd),
        ]
        validate_socketio_msg(g.clients, validators)
        assert not fr_client.exists("game:1234:activity")
        assert fr_client.hget(f'game:1234:player:{player("0")}', "points") == "1"
        assert fr_client.hget("game:1234:info", "current_section") == str(
            Section.RESTART.value
        )


def test_v_memer_votes_raises_exception():
    with NewGame(section="vote", filled=True) as g:
        g.clients[0].emit("voteSubmit", 10, namespace="/game")
        validate_socketio_msg(
            g.clients[:1],
            [
                M.default_msg(
                    "gameException",
                    "[Vote] Invalid or duplication player's id in activity list",
                )
            ],
        )


def test_v_voter_votes_invalid_score_raises_exception():
    with NewGame(section="vote", filled=True) as g:
        g.clients[1].emit("voteSubmit", 11, namespace="/game")
        validate_socketio_msg(
            g.clients[1:2], [M.default_msg("gameException", "[Vote] Invalid score")]
        )


def test_v_voter_votes_empty_score_does_nothing():
    with NewGame(section="vote", filled=True) as g:
        # clear previous messages first
        g.clients[1].get_received(namespace="/game")

        g.clients[1].emit("voteSubmit", "", namespace="/game")
        assert g.clients[1].get_received(namespace="/game") == []


def test_v_voter_disconnects():
    # shouldn't have any big changes
    with NewGame(section="vote", filled=True) as g:
        g.clients[1].disconnect(namespace="/game")
        g.clients.pop(1)
        validate_socketio_msg(
            g.clients,
            [
                M.default_msg("gamePlayerDisconnected", g.clients_id[1]),
            ],
        )


def test_v_last_voter_disconnects():
    # game should proceed to next memer
    with NewGame(section="vote", filled=True) as g:
        total_points = 0
        validators = []
        # exclude first and last player
        for i, client in enumerate(g.clients[1:-1]):
            score = random.choice([0, 5, 10])
            client.emit("voteSubmit", score, namespace="/game")
            total_points += score
            validators.append(M.default_msg("gamePlayerReady", g.clients_id[i + 1]))
        g.clients[-1].disconnect(namespace="/game")
        validate_socketio_msg(
            g.clients[:-1],
            [
                M.default_msg("gamePlayerDisconnected", g.clients_id[-1]),
                M.gameStart(memer=player("1"), rounds_remain=g.total_rounds - 1),
            ],
        )


def test_v_memer_disconnects():
    # The game should proceed to pick the next memer
    with NewGame(section="vote", filled=True) as g:
        g.clients[0].disconnect(namespace="/game")

        validate_socketio_msg(
            g.clients[1:],
            [
                M.default_msg("gamePlayerDisconnected", g.clients_id[0]),
                M.gameStart(memer=player("1"), rounds_remain=g.total_rounds - 1),
                M.default_msg("gameReason", "Memer disconnected"),
            ],
        )


################################################################


################################  NEW SECTION ################################
def test_r_scenario_1():
    # players ready to play a new game.
    with NewGame(section="restart", filled=True) as g:
        g.game.rounds_remain = 0
        # Add dummy captions
        for i in range(len(g.clients)):
            score = 5
            fr_client.hset(
                f"game:1234:player:{player(i)}:caption", "key", f"test_fingerprint{i}"
            )
            fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", score)

        # Add some dummy points to the 2nd and 4rd players
        fr_client.hset(f"game:1234:player:{player('1')}", "points", 1)
        fr_client.hset(f"game:1234:player:{player('3')}", "points", 1)

        validators = []
        # Now simulate the event
        for i, client in enumerate(g.clients):
            client.emit("playerReady", namespace="/game")
            validators.append(M.default_msg("gamePlayerReady", g.clients_id[i]))

        validators.append(M.gameStart(memer=player("0"), rounds_remain=g.total_rounds - 1))
        validators.append(M.default_msg("gameTimeUp"))
        validators.append(M.default_msg("gameTimeStart", g.duration))
        validate_socketio_msg(g.clients, validators)

        assert not fr_client.exists("game:1234:activity")
        assert fr_client.hget("game:1234:info", "rounds_remain") == str(g.total_rounds - 1)
        assert fr_client.hget("game:1234:info", "current_section") == "1"
        assert fr_client.hget("game:1234:info", "current_memer") == player("0")
        assert fr_client.hget("game:1234:info", "current_memer_idx") == "0"
        assert fr_client.llen('game:1234:players') == 5
        for pid in g.clients_id:
            assert not fr_client.exists(f"game:1234:player:{pid}:caption")
            assert fr_client.hget(f"game:1234:player:{pid}", "points") == "0"


def test_r_one_disconnect():
    # All clicks 'next' but one disconnects
    # the game should start a fresh game
    with NewGame(section='restart', filled=True) as g:
        g.game.rounds_remain = 0
        # Add dummy captions
        for i in range(len(g.clients)):
            score = 5
            fr_client.hset(
                f"game:1234:player:{player(i)}:caption", "key", f"test_fingerprint{i}"
            )
            fr_client.hset(f"game:1234:player:{player(i)}:caption", "score", score)

        # Add some dummy points to the 2nd and 4rd players
        fr_client.hset(f"game:1234:player:{player('1')}", "points", 1)
        fr_client.hset(f"game:1234:player:{player('3')}", "points", 1)

        validators = []
        # Now simulate the event
        for i, client in enumerate(g.clients[:-1]):
            client.emit("playerReady", namespace="/game")
            validators.append(M.default_msg("gamePlayerReady", g.clients_id[i]))

        g.clients[-1].disconnect(namespace='/game')
        validators.append(M.default_msg("gamePlayerDisconnected", player("4")))
        validators.append(M.gameStart(memer=player("0"), rounds_remain=g.total_rounds - 1))
        validators.append(M.default_msg("gameTimeUp"))
        validators.append(M.default_msg("gameTimeStart", g.duration))
        validate_socketio_msg(g.clients[:-1], validators)

        assert not fr_client.exists("game:1234:activity")
        assert fr_client.hget("game:1234:info", "rounds_remain") == str(g.total_rounds - 1)
        assert fr_client.hget("game:1234:info", "current_section") == "1"
        assert fr_client.hget("game:1234:info", "current_memer") == player("0")
        assert fr_client.hget("game:1234:info", "current_memer_idx") == "0"
        assert fr_client.llen('game:1234:players') == 4
        for pid in g.clients_id[:-1]:
            assert not fr_client.exists(f"game:1234:player:{pid}:caption")
            assert fr_client.hget(f"game:1234:player:{pid}", "points") == "0"

