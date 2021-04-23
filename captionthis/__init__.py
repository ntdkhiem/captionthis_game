import os
from logging.config import dictConfig

from celery import Celery
from flask import Flask
from flask.logging import default_handler
from flask_redis import FlaskRedis
from flask_socketio import SocketIO
from flask_cors import CORS

from config import config

from .errors import register as register_errors

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)


socketio = SocketIO()
redis_client = FlaskRedis(decode_responses=True, encoding="utf-8")
celery = Celery(
    __name__,
    broker=os.environ.get("CELERY_BROKER_URL"),
    backend=os.environ.get("CELERY_BROKER_URL"),
)
celery.config_from_object("celeryconfig")

# Import celery task so that it is registered with the Celery workers
from .timers import times_up  # noqa
from .tasks import filterer  # noqa

# Import Socket.IO events so that they are registered with Flask-SocketIO
# from .events import GameNamespace
from .events import GameNamespace


def create_app(config_name=None, main=True) -> Flask:
    """
    Flask instance of game service
    """
    if config_name is None:
        config_name = os.environ.get("CAPTIONTHIS_CONFIG", "development")
    app: Flask = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    if main:
        # Initialize socketio server and attach it to the message queue, so
        # that everything works even when there are multiple servers or
        # additional processes such as Celery workers wanting to access
        # Socket.IO
        socketio.init_app(app, message_queue=app.config["SOCKETIO_MESSAGE_QUEUE"], cors_allowed_origins=[])
    else:
        # Initialize socketio to emit events through through the message queue
        # Note that since Celery does not use eventlet, we have to be explicit
        # in setting the async mode to not use it.
        socketio.init_app(
            None,
            message_queue=app.config["SOCKETIO_MESSAGE_QUEUE"],
            async_mode="threading",
        )

    CORS(app)

    if not app.testing:
        redis_client.init_app(app)

    # Import routes
    from .game import game_bp

    app.register_blueprint(game_bp)

    socketio.on_namespace(GameNamespace("/game"))

    # Register error handlers
    register_errors(app)

    if not app.debug:
        # Register sentry errors/exceptions watcher
        if app.config.get("SENTRY_DSN"):
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration

            sentry_sdk.init(
                dsn=app.config["SENTRY_DSN"], integrations=[FlaskIntegration()]
            )

    # Setup logger
    app.logger.removeHandler(default_handler)
    app.logger.info("[+] CaptionThis SocketIO startup...")

    return app
