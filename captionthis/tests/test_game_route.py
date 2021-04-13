import pytest
from pytest_mock.plugin import MockerFixture

from ..api.controllerAPI import ControllerAPI

from .base import fr_client, app


@pytest.fixture
def client(mocker: MockerFixture):
    with app.test_client() as client:
        with mocker.patch("captionthis.api.controllerAPI.redis_client", fr_client):
            yield client


def test_get_game(client):
    rv = client.get("/game")
    assert rv.status_code == 200
    assert rv.json["data"] == []

    # Non-existening game's id
    rv = client.get("/game?id=1234")
    assert rv.status_code == 200
    assert rv.json["data"] == {}

    ControllerAPI.create_game("5", "2", "10", "1234")
    rv = client.get("/game?id=1234")
    assert rv.status_code == 200
    assert rv.json["data"] == {
        "g_status": "0",
        "g_info": {
            "max_players": "5",
            "total_rounds": "2",
            "duration": "10",
            "rounds_remain": "2",
            "current_section": "0",
            "current_memer": "",
            "current_memer_idx": "0",
        },
    }
    rv = client.get("/game")
    assert rv.json["data"] == ["1234"]


def test_post_game(client, mocker: MockerFixture):
    mocker.patch(
        "captionthis.api.controllerAPI.generate_game_id",
        return_value="1235",
    )
    rv = client.post(
        "/game", data={"total_rounds": "2", "total_players": "5", "duration": "10"}
    )
    assert rv.status_code == 200
    assert rv.json["data"] == "1235"

    rv = client.post("/game", data={"total_players": "5", "duration": "10"})
    assert rv.status_code == 400

    rv = client.post("/game", data={"total_rounds": "2", "duration": "10"})
    assert rv.status_code == 400

    rv = client.post("/game", data={"total_rounds": "2", "total_players": "5"})
    assert rv.status_code == 400

    rv = client.post(
        "/game", data={"total_rounds": "a", "total_players": "5", "duration": "10"}
    )
    assert rv.status_code == 400
