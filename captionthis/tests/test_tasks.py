from pytest import fixture
from pytest_mock.plugin import MockerFixture

from ..tasks import times_up, filterer
from .base import app, fr_client


@fixture()
def patch_redis(mocker: MockerFixture):
    mocker.patch("captionthis.tasks.redis_client", fr_client)
    yield


def test_times_up(patch_redis, mocker: MockerFixture):
    # mock functions that are outside of the task
    mocker.patch("captionthis.wsgi_aux.app", app)
    m_captionthis = mocker.patch("captionthis.api.captionthisAPI.CaptionThis")
    m_captionthis.return_value = "game's instance"
    m_next_player_turn = mocker.patch("captionthis.helpers.next_player_turn")
    m_switch_to = mocker.patch("captionthis.helpers.switch_to")

    # add related dummy data
    fr_client.set("game:1234", "1")
    fr_client.set("game:1234:timer", "data")
    mocked_game_info = {
        "max_players": "5",
        "total_rounds": "2",
        "duration": "10",
        "rounds_remain": "1",
        "current_section": "1",
        "current_memer": "memer0",
        "current_memer_idx": "0",
    }
    fr_client.hmset("game:1234:info", mocked_game_info)

    times_up("1234")

    m_captionthis.assert_called_with("1234", "1", **mocked_game_info)
    m_next_player_turn.assert_called_with("game's instance")
    m_switch_to.assert_called_with("caption", "game's instance")
    assert not fr_client.exists("game:1234:timer")


def test_filterer(patch_redis):
    # dummy data
    fr_client.set("game:1234", "0")
    fr_client.set("game:1234:info", 'game"s info')
    fr_client.lpush("games", "1234")
    fr_client.set("game:1235:info", 'game"s info')
    fr_client.lpush("games", "1235")

    filterer()

    assert fr_client.exists("game:1234")
    assert fr_client.exists("game:1234:info")
    assert not fr_client.exists("game:1235:info")
    games = fr_client.lrange("games", 0, -1)
    assert "1234" in games
    assert not "1235" in games
