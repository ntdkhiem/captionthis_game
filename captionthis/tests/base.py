import fakeredis
import pytest
from pytest_mock.plugin import MockerFixture

from .. import create_app


fr_client = fakeredis.FakeStrictRedis(decode_responses=True, encoding="utf-8")
PLAYER_NS = "ra4d{}m"


app = create_app(config_name="testing")


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    template_ids = ["templateID1"]
    template = {
        "name": "Ancient Aliens Guy",
        "key": "aag",
        "lines": "2",
        "styles": [],
        "example": "http://dummy_url_from_memegen",
        "source": "http://knowyourmeme.com/memes/ancient-aliens",
    }
    if args[0] == "http://memegen:5000/templates":
        return MockResponse(template_ids, 200)
    elif "images" in args[0]:
        return MockResponse("test_fingerprint", 200)
    elif len(args[0]) > len("http://memegen:5000/templates"):
        return MockResponse(template, 200)

    return MockResponse(None, 404)


@pytest.fixture(autouse=True)
def patch_redis(mocker: MockerFixture):
    mocker.patch("captionthis.helpers.remove_timer")
    mocker.patch("captionthis.helpers.start_timer")
    mocker.patch("captionthis.timers.redis_client", fr_client)
    mocker.patch("captionthis.api.controllerAPI.redis_client", fr_client)
    mocker.patch("captionthis.api.captionthisAPI.redis_client", fr_client)
    mocker.patch(
        "captionthis.api.memegenAPI.requests.get",
        side_effect=mocked_requests_get,
    )
    mocker.patch(
        "captionthis.api.memegenAPI.requests.delete",
        side_effect=mocked_requests_get,
    )
    yield
    # Clean up after every call
    items = fr_client.scan()
    if items[0] != 0:
        while items[0] != 0:
            temp_items = items
            items = fr_client.scan(items[0])
            for item in temp_items[1]:
                fr_client.delete(item)
    # Make sure to delete all items when items[0] == 0
    for item in items[1]:
        fr_client.delete(item)


def player(i):
    return PLAYER_NS.format(i)
