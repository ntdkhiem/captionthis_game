from pytest import fixture
from pytest_mock.plugin import MockerFixture

from ..timers import remove_timer, start_timer

from .base import fr_client


@fixture()
def patch_redis(mocker: MockerFixture):
    mocker.patch("captionthis.timers.redis_client", fr_client)
    yield


class Mocked_Task_Result:
    def __init__(self):
        self.id = "dummy_task_id"


def test_timer(patch_redis, mocker: MockerFixture):
    m_times_up = mocker.patch("captionthis.tasks.times_up.apply_async")
    m_times_up.return_value = Mocked_Task_Result()

    start_timer("1234", "120")

    m_times_up.assert_called_once_with(("1234",), countdown="120", ignore_result=True)

    assert fr_client.hgetall("game:1234:timer") == {
        "duration": "120",
        "task_id": "dummy_task_id",
    }

    m_celery = mocker.patch("captionthis.timers.celery.control.revoke")
    remove_timer("1234")

    assert not fr_client.exists("game:1234:timer")
    m_celery.assert_called_once_with("dummy_task_id")
