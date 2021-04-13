from typing import Tuple, Dict
from werkzeug.exceptions import HTTPException, InternalServerError


class CaptionThisError(Exception):
    def __init__(self, msg="Invalid Request"):
        self.msg = msg


class InvalidTotalPlayers(CaptionThisError):
    pass


class InvalidTotalRounds(CaptionThisError):
    pass


class InvalidDuration(CaptionThisError):
    pass


class ActivityError(CaptionThisError):
    pass


class CaptionError(CaptionThisError):
    pass


class VoteError(CaptionThisError):
    pass


def register(app):
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(500)
    def handle_http_error(e) -> Tuple[Dict, int]:
        if not isinstance(e, HTTPException):
            e = InternalServerError()

        data = getattr(e, "data", None)
        if data:
            message = data["message"]
        else:
            message = e.description
        return dict(errors=message), e.code

    @app.errorhandler(CaptionThisError)
    def on_captionthis_error(e):
        return dict(errors=e.msg), 400
