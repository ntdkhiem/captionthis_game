from flask import request, current_app
from flask_socketio import Namespace, close_room, emit, join_room

from .api.captionthisAPI import CaptionThis
from .api.controllerAPI import Client, ControllerAPI

from .api.memegenAPI import create_meme, delete_game_assets

from . import socketio
from .utils import Section
from .helpers import ingame_only, next_player_turn, switch_to


class GameNamespace(Namespace):
    def on_connect(self):
        game_id = request.args.get("id")
        nickname = request.args.get("name")
        if not all([game_id, nickname]):
            return False
        data = ControllerAPI.join_game(game_id, nickname)
        if not all(data.values()):
            return False
        join_room(game_id)
        ControllerAPI.add_client(request.sid, data["p_id"], game_id)
        emit(
            "gameConnected",
            [
                data["p_id"],
                data["g_players"],
                data["g_info"]["total_rounds"],
            ],
        )
        emit(
            "gamePlayerConnected",
            {data["p_id"]: data["g_players"].get(data["p_id"])},
            room=game_id,
        )
        if len(data["g_players"]) >= 3:
            emit("gameReady", room=game_id)
        if data["g_status"] == "2":
            emit("gameFull", room=game_id)

    @ingame_only
    def on_playerReady(self, player: Client = None, game: CaptionThis = None):
        game.player_ready(player.id)
        emit("gamePlayerReady", player.id, room=player.gid)
        if game.all_ready():
            if game.current_section == Section.WAIT.value:
                game.reset()
            elif game.current_section == Section.RESTART.value:
                game.reset(new_game=True)
            game.start_game()
            game.set_next_memer()
            switch_to("caption", game)

    @ingame_only
    def on_captionSubmit(
        self, data, player: Client = None, game: CaptionThis = None
    ) -> None:
        if (key := data.get("key")) and (lines := data.get("lines")):
            fingerprint = create_meme(key, lines, player.gid)
            game.add_meme(player.id, fingerprint)
            emit("gamePlayerReady", player.id, room=player.gid)
            switch_to("vote", game)

    @ingame_only
    def on_voteSubmit(
        self, data, player: Client = None, game: CaptionThis = None
    ) -> None:
        if data or data == 0:
            game.vote(player.id, int(data))
            emit("gamePlayerReady", player.id, room=player.gid)

            if game.all_ready():
                emit("gameGetScore", game.caption["score"], room=player.gid)
                if next_player_turn(game):
                    switch_to("caption", game)

    def on_disconnect(self):
        if player := ControllerAPI.remove_client(request.sid):
            current_app.logger.info(f"Client {request.sid} disconnecting...")
            if room := ControllerAPI.game(player.gid):
                game = CaptionThis(player.gid, room["g_status"], **room["g_info"])
                ControllerAPI.kick(player.gid, player.id)
                emit("gamePlayerDisconnected", player.id, room=player.gid)
                if game.is_playable():
                    if (
                        game.current_section == Section.WAIT.value
                        or game.current_section == Section.RESTART.value
                    ):
                        if len(game.players) - len(game.activity_list) == 0:
                            if game.current_section == Section.RESTART.value:
                                game.reset(new_game=True)
                            game.set_next_memer()
                            game.start_game()
                            switch_to("caption", game)
                        elif game.status == "2":
                            game.status = "0"
                            game.commit()
                            emit("gameOpen", room=player.gid)
                    elif game.current_section == Section.CAPTION.value:
                        if game.current_memer == player.id:
                            # choose next memer then go to caption section
                            if not game.set_next_memer():
                                game.start_game()
                            emit("gameReason", "Memer disconnected", room=player.gid)
                            switch_to("caption", game)
                    elif game.current_section == Section.VOTE.value:
                        if game.current_memer == player.id:
                            # choose next memer then go to caption section
                            if not game.set_next_memer():
                                game.start_game()
                            emit("gameReason", "Memer disconnected", room=player.gid)
                            switch_to("caption", game)
                            return
                        # exclude memer
                        if len(game.players) - 1 - len(game.activity_list) == 0:
                            game.set_next_memer()
                            switch_to("caption", game)
                else:
                    # remove if the game is not in wait with 1 or more players
                    if (game.current_section != Section.WAIT.value) or (
                        game.current_section == Section.WAIT.value
                        and len(game.players) == 0
                    ):
                        emit("gameDisconnected", room=player.gid)
                        close_room(player.gid)
                        ControllerAPI.remove_game(player.gid)
                        delete_game_assets(player.gid)
                        current_app.logger.info(f"Close room {player.gid}")

    def on_message(self, msg) -> None:
        current_app.logger.info(f"Foreign message from {request.sid}", msg)

    def on_error(self, e) -> None:
        current_app.logger.warning(f"SocketIO failed to connect: {e}")
