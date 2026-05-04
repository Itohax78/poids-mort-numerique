"""
seed.py — Crée un jeu de données de démonstration.

Usage : `python -m database.seed`

Crée :
  - 1 admin   (admin@example.com / admin1234)
  - 2 users   (alice@example.com / alice1234, bob@example.com / bob1234)
  - quelques services par user pour illustrer le score.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models


def seed():
    models.init_db()

    # Si un compte existe déjà, on ne ré-initialise pas pour ne
    # pas dupliquer (idempotence partielle).
    if models.count_users() > 0:
        print("Base déjà peuplée — abandon.")
        return

    admin_id = models.create_user("admin",  "admin@example.com",  "admin1234", role="admin")
    alice_id = models.create_user("alice",  "alice@example.com",  "alice1234")
    bob_id   = models.create_user("bob",    "bob@example.com",    "bob1234")

    cats = {c["nom"]: c["id"] for c in models.list_categories()}

    # Alice : un peu de tout, score moyen
    models.create_service(alice_id, "Compte LinkedIn",          cats["Reseau social"], "actif")
    models.create_service(alice_id, "Compte Twitter (jamais)",  cats["Reseau social"], "supprime")
    models.create_service(alice_id, "Newsletter Le Monde",      cats["Newsletter"],    "dormant")
    models.create_service(alice_id, "Compte Dropbox",           cats["Cloud"],         "supprime")
    models.create_service(alice_id, "Compte Spotify",           cats["Streaming"],     "actif")

    # Bob : tout actif, score bas
    models.create_service(bob_id,   "Instagram",                cats["Reseau social"], "actif")
    models.create_service(bob_id,   "Google Drive",             cats["Cloud"],         "actif")
    models.create_service(bob_id,   "Netflix",                  cats["Streaming"],     "actif")

    print(f"Comptes créés : admin (id={admin_id}), alice (id={alice_id}), bob (id={bob_id})")
    print("Mots de passe : admin1234 / alice1234 / bob1234")


if __name__ == "__main__":
    seed()
