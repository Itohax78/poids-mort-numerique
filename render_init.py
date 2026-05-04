"""
render_init.py — Script d'initialisation pour le déploiement Render.

Exécuté avant Gunicorn dans le startCommand de render.yaml.

Logique :
  - Si la BDD existe déjà (cas d'un redémarrage à chaud), on ne fait rien.
  - Sinon (premier démarrage ou cold-start sur filesystem éphémère du
    free tier), on lance le seed qui crée le schéma + un jeu de données
    de démonstration. Le seed lui-même est idempotent : il n'écrase
    aucun compte existant.

Usage : `python render_init.py`
"""

import os
import sys

# Même résolution que app/models.py pour rester cohérent.
DB_PATH = os.environ.get(
    "POIDS_MORT_DB",
    os.path.join(os.path.dirname(__file__), "database", "poids_mort.db"),
)


def main():
    if os.path.exists(DB_PATH):
        print(f"[init] BDD présente ({DB_PATH}) — aucun seed.")
        return 0

    print(f"[init] BDD absente ({DB_PATH}) — initialisation + seed.")
    # Import différé : évite de toucher à la BDD si on n'en a pas besoin.
    from database.seed import seed
    seed()
    return 0


if __name__ == "__main__":
    sys.exit(main())
