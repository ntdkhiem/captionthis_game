from flask import render_template

from . import contact_bp


@contact_bp.route("/")
def index():
    return render_template("contact.html")
