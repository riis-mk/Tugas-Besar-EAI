"""
Keuangan service entry point.

Flask handles /health (JSON REST).
Spyne WsgiApplication is mounted at /soap via Werkzeug DispatcherMiddleware,
so WSDL is at GET /soap?wsdl and requests are POSTed to /soap.
"""
import logging

from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

from app.soap_service import wsgi_soap_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

flask_app = Flask(__name__)


@flask_app.route("/health")
def health():
    return {"status": "ok", "service": "keuangan"}


# Mount the Spyne WSGI app under /soap
application = DispatcherMiddleware(flask_app, {"/soap": wsgi_soap_app})


if __name__ == "__main__":
    from waitress import serve
    logging.getLogger().info("Keuangan SOAP service starting on :8000 …")
    serve(application, host="0.0.0.0", port=8000)
