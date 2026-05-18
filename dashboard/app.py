"""
dashboard/app.py — Flask web dashboard for the trading bot.

Runs in a background thread alongside the bot.
Access at: http://localhost:5000
"""

import logging
from flask import Flask, jsonify, render_template
from src.state import bot_state

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)   # suppress Flask request logs in the terminal

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def state():
    """Returns the full bot state as JSON. Polled every 5s by the dashboard."""
    return jsonify(bot_state.get())


def run_dashboard(host: str = "0.0.0.0", port: int = 5000) -> None:
    """Call this in a daemon thread from main.py."""
    app.run(host=host, port=port, debug=False, use_reloader=False)
