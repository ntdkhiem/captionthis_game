import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "51f52814-0071-11e6-a247-000ec6c2372c")
    SOCKETIO_MESSAGE_QUEUE = os.environ.get(
        "SOCKETIO_MESSAGE_QUEUE", os.environ.get("CELERY_BROKER_URL", "redis://")
    )
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis")
    DEFAULT_VOTE_DURATION = 120
    IMAGES_DIRECTORY = os.environ.get("IMAGES_DIRECTORY", "")
    TIME_DELAY = 2  # in seconds
    VOTE_WAIT_TIME = 2  # in seconds


class DevelopmentConfig(Config):
    TIME_DELAY = 0.5
    DEBUG = True


class ProductionConfig(Config):
    TIME_DELAY = 5


class TestingConfig(Config):
    TESTING = True
    SOCKETIO_MESSAGE_QUEUE = None
    TIME_DELAY = 0


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
