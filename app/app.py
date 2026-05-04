"""
app.py — Point d'entrée de l'application Flask.

Pattern factory : permet de tester et de configurer plus facilement.
Aucune dépendance optionnelle : juste Flask (qui inclut Jinja2 et
Werkzeug). Le total des dépendances tient en 2 lignes dans
requirements.txt.

Optimisations Green IT intégrées :
  - compression gzip à la volée des réponses HTML/CSS/JS
    (réduction d'environ 65 % du volume transféré, sans
    bibliothèque externe : on utilise gzip de la stdlib)
  - en-têtes de cache long pour les ressources statiques
    (CSS chargé une seule fois pour toute une session de visite)
"""

import os
import gzip
import io
from flask import Flask, request

from . import models, routes


def _gzip_response(response):
    """Compresse les réponses textuelles si le client l'accepte."""
    accept = request.headers.get("Accept-Encoding", "")
    if (
        "gzip" not in accept
        or response.status_code < 200
        or response.status_code >= 300
        or "Content-Encoding" in response.headers
    ):
        return response
    ctype = response.content_type or ""
    if not (ctype.startswith("text/") or "javascript" in ctype or "json" in ctype):
        return response
    # Désactive le mode passthrough utilisé par send_file pour les statics
    response.direct_passthrough = False
    data = response.get_data()
    if len(data) < 500:  # inutile sous 500 octets (overhead gzip)
        return response
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as gz:
        gz.write(data)
    response.set_data(buf.getvalue())
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    response.headers.add("Vary", "Accept-Encoding")
    return response


def create_app():
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Clé secrète : obligatoire pour les sessions signées.
    # En production, elle DOIT venir d'une variable d'environnement.
    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY",
        "dev-key-changeme-en-production",
    )

    # Sécurité des cookies de session.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # En production (HTTPS), passer à True via env.
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("FLASK_ENV") == "production"
    )

    # On limite la taille des requêtes pour éviter les abus
    # (utile même sans upload : aucune raison qu'un formulaire
    # texte dépasse 64 Ko).
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    # Initialisation BDD au premier démarrage (idempotent).
    models.init_db()

    # Enregistrement du blueprint principal.
    app.register_blueprint(routes.bp)

    # Cache long pour les ressources statiques : 1 jour.
    # Combiné au CSS minifié, le navigateur ne recharge pas la
    # feuille à chaque navigation interne.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400

    # Compression gzip à la volée — sans dépendance externe.
    app.after_request(_gzip_response)

    return app


# Pour `flask --app app.app run` ou Gunicorn.
app = create_app()


if __name__ == "__main__":
    # Mode développement local uniquement.
    app.run(host="127.0.0.1", port=5000, debug=True)
