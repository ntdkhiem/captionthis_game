import pytest
from pytest_mock import MockerFixture

from ..api.memegenAPI import get_meme, Template, create_meme
from .base import mocked_requests_get


def test_get_meme(mocker: MockerFixture):
    m_req = mocker.patch(
        "captionthis.api.memegenAPI.requests.get",
        side_effect=mocked_requests_get,
    )
    t: Template = get_meme()
    template = {
        "name": "Ancient Aliens Guy",
        "key": "aag",
        "lines": "2",
        "styles": [],
        "example": "http://dummy_url_from_memegen",
        "source": "http://knowyourmeme.com/memes/ancient-aliens",
    }
    assert t._asdict() == template
    assert len(m_req.call_args_list) == 2


def test_create_meme(mocker: MockerFixture):
    m_req = mocker.patch(
        "captionthis.api.memegenAPI.requests.get",
        side_effect=mocked_requests_get,
    )
    fingerprint = create_meme("aag", "hello world", "1234")
    assert fingerprint == "test_fingerprint"
    assert len(m_req.call_args_list) == 1
