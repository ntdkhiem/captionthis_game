from flask import render_template

from . import about_bp


@about_bp.route("/")
def index():
    return render_template("about.html")
