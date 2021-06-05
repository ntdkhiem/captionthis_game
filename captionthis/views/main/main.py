import random

from requests.exceptions import Timeout, ConnectionError
from flask import render_template, request, current_app, send_from_directory

from . import main_bp
from .forms import JoinGameForm, CreateGameForm
from ...utils import response_formatter, error_formatter
from ...api.controllerAPI import ControllerAPI


@main_bp.route("/")
def index():
    join_form = JoinGameForm()
    create_form = CreateGameForm()
    return render_template("game.html", join_form=join_form, create_form=create_form)


@main_bp.route('/image/<path:path>')
def serve_image(path):
    return send_from_directory(current_app.config['IMAGES_DIRECTORY'], path)


@main_bp.route("/join", methods=["POST"])
def join_room():
    join_form = JoinGameForm(request.form)
    response = ""

    if join_form.validate():
        game_id = join_form.game_id.data

        game = ControllerAPI.game(game_id)
        if game:
            status = game['g_status']
            if status == "0":
                response = dict(id=game_id)
            elif status == "2":
                response = "Game is full"
            else:
                response = "Game is currently playing"
        else:
            response = f"Game does not exist"
    if response:
        return response_formatter(response)

    return response_formatter(join_form.errors, 400)


        # try:
        #     data, err = GameAPI.request_join_game(game_id)
        # except (Timeout, ConnectionError):
        #     current_app.logger.warning("Communicate with server failed in /join")
        #     return response_formatter("Communication with server failed")

        # if data:
        #     game_status = data["g_status"]
        #     if game_status == "0":
        #         return_data = dict(id=game_id)
        #     elif game_status == "2":
        #         return_data = "Game is full"
        #     else:
        #         return_data = "Game is currently playing"
        # else:
        #     return_data = f"Game does not exist: {err}"

    # if return_data:
    #     return response_formatter(return_data)

    # return error_formatter(join_form.errors)


@main_bp.route("/joinRandom", methods=["POST"])
def join_random_room():
    open_games = ControllerAPI.games()
    # try:
    #     data = GameAPI.request_open_games()
    # except (Timeout, ConnectionError):
    #     current_app.logger.warning("Communicate with server failed in /joinRandom")
    #     return response_formatter("Communicate with server failed")

    if open_games and len(open_games) != 0:
        room = random.choice(open_games)
        return response_formatter(dict(id=room))
    return response_formatter("cannot find a room to join")


@main_bp.route("/create", methods=["POST"])
def create_room():
    create_form = CreateGameForm(request.form)

    if create_form.validate():
        # payload = {
        #     "total_rounds": create_form.total_games.data,
        #     "total_players": create_form.total_players.data,
        #     "duration": create_form.duration.data,
        # }
        game_id = ControllerAPI.create_game(
            create_form.total_players.data,
            create_form.total_games.data,
            create_form.duration.data,
        )
        current_app.logger.info(f"New game created [{game_id}]")
        # try:
        #     data = GameAPI.request_create_game(payload)
        # except (Timeout, ConnectionError):
        #     current_app.logger.error("Could not make request to the server")
        #     return response_formatter("Communication to server failed")
        # except Exception as e:
        #     current_app.logger.error(f"Failed to communicate to server: {e}")
        #     return response_formatter("Failed to communicate to server")

        return response_formatter(dict(id=game_id))

    return response_formatter(create_form.errors, 400)
