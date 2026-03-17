"""BudBridge Flask HTTP server — runs in a background daemon thread."""

from __future__ import annotations

import logging
import secrets
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

# Flask is imported lazily so the module can be imported without it installed
# during unit tests that mock it.
_flask_app = None
_server_thread: Optional[threading.Thread] = None
_shutdown_event = threading.Event()

# Werkzeug server reference for graceful shutdown
_werkzeug_server = None


def _make_app(config, handoff_fn: Callable):
    """Build and return the Flask application."""
    from flask import Flask, jsonify, request, abort

    app = Flask("BudBridge")
    app.config["PROPAGATE_EXCEPTIONS"] = True

    # Silence Flask/Werkzeug request logs (we use our own)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # Security middleware
    # ------------------------------------------------------------------

    @app.before_request
    def _check_origin():
        remote = request.remote_addr
        allowed = {"127.0.0.1", "::1", config.network.phone_ip}
        if remote not in allowed:
            log.warning("Rejected request from %s", remote)
            abort(403)

        secret = config.network.shared_secret
        if secret:
            token = request.headers.get("X-BudBridge-Token", "")
            if not secrets.compare_digest(token, secret):
                log.warning("Bad or missing X-BudBridge-Token from %s", remote)
                abort(403)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get("/ping")
    def ping():
        return jsonify({"alive": True, "app": "BudBridge", "version": "1.0"})

    @app.get("/status")
    def status():
        from budbridge import bluetooth
        connected = bluetooth.is_connected(config)
        return jsonify(
            {
                "connected": connected,
                "device": config.device.bt_friendly_name,
            }
        )

    @app.post("/release")
    def release():
        result = handoff_fn()
        if result is None:
            # Handoff in progress
            return jsonify({"error": "Handoff already in progress"}), 409
        return jsonify(result)

    return app


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_server(config, handoff_fn: Callable) -> None:
    """Start the Flask server in a background daemon thread."""
    global _flask_app, _server_thread, _werkzeug_server, _shutdown_event

    _shutdown_event.clear()

    _flask_app = _make_app(config, handoff_fn)

    def _run():
        global _werkzeug_server
        from werkzeug.serving import make_server

        try:
            srv = make_server("0.0.0.0", config.network.pc_port, _flask_app)
            _werkzeug_server = srv
            log.info("BudBridge HTTP server listening on port %d", config.network.pc_port)
            srv.serve_forever()
        except Exception as exc:
            log.error("HTTP server error: %s", exc)

    _server_thread = threading.Thread(target=_run, name="BudBridge-HTTP", daemon=True)
    _server_thread.start()


def stop_server() -> None:
    """Gracefully shut down the HTTP server."""
    global _werkzeug_server
    if _werkzeug_server is not None:
        try:
            _werkzeug_server.shutdown()
            log.info("BudBridge HTTP server stopped.")
        except Exception as exc:
            log.warning("Error stopping HTTP server: %s", exc)
        _werkzeug_server = None
