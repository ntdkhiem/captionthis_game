from flask_wtf import FlaskForm
from wtforms.fields import IntegerField
from wtforms.validators import InputRequired, NumberRange


class JoinGameForm(FlaskForm):
    game_id = IntegerField(
        "Game",
        validators=[
            InputRequired(message="Must contain 4 digits"),
            NumberRange(min=1000, max=9999, message="Must contain 4 digits"),
        ],
    )


class CreateGameForm(FlaskForm):
    total_games = IntegerField(
        "Total Games",
        default=2,
        validators=[NumberRange(min=1, max=10, message="Must be between 1 and 10")],
    )
    total_players = IntegerField(
        "Total Players",
        default=5,
        validators=[NumberRange(min=3, message="Must be at least 3 players")],
    )
    duration = IntegerField(
        "Duration(second) Per Caption",
        default=10,
        validators=[NumberRange(min=10, message="Must be at least 10 seconds")],
    )
