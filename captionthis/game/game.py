from flask import request, abort, current_app

from . import game_bp
from ..api.controllerAPI import ControllerAPI
from ..utils import error_formatter, response_formatter


@game_bp.route("/game", methods=["GET", "POST"])
def index():
    """
    GET: returns a game's status if given an ID or all open games
    POST: calls game's controller to create a game then returns the game's id
    """
    if request.method == "GET":
        game_id = request.args.get("id")
        if game_id and game_id.isdigit():
            if game := ControllerAPI.game(game_id):
                return response_formatter(game)
            else:
                return response_formatter({})
        else:
            return response_formatter(ControllerAPI.games())

    elif request.method == "POST":
        total_rounds = request.form.get("total_rounds")
        total_players = request.form.get("total_players")
        duration = request.form.get("duration")

        bools = [
            (not var or not var.isdigit())
            for var in [total_rounds, total_players, duration]
        ]
        if any(bools):
            abort(400)

        game_id = ControllerAPI.create_game(total_players, total_rounds, duration)
        current_app.logger.info(f"New game created [{game_id}]")

        if game_id.isdigit():
            return response_formatter(game_id)
        return error_formatter(game_id)
