"""
tests.py — Tests fonctionnels et de sécurité.

Lance les scénarios listés dans le rapport (Phase 6 du sujet)
et imprime un tableau OK / KO. Aucun framework de test externe
n'est requis : on utilise unittest (stdlib).

Usage : `python -m tests.tests`
"""

import os
import sys
import unittest

# Permet d'importer l'app depuis la racine du dépôt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# On utilise une base de test isolée
os.environ["POIDS_MORT_DB"] = "/tmp/poids_mort_test.db"
if os.path.exists("/tmp/poids_mort_test.db"):
    os.remove("/tmp/poids_mort_test.db")

from app.app import app
from app import models


class PoidsMortTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # On démarre toujours sur une base vierge.
        if os.path.exists("/tmp/poids_mort_test.db"):
            os.remove("/tmp/poids_mort_test.db")
        models.init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config["TESTING"] = True

    # --------------------------------------------------------
    # Scénarios fonctionnels (Phase 6.1 du sujet)
    # --------------------------------------------------------

    def test_01_creer_utilisateur_valide(self):
        """Créer un utilisateur valide → enregistré + redirection."""
        r = self.client.post(
            "/inscription",
            data={"pseudo": "testuser", "email": "test@test.fr", "mot_de_passe": "abcdef12"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Compte cr", r.data)  # message flash de succès

    def test_02_creer_utilisateur_email_vide(self):
        """Créer un utilisateur avec email vide → erreur."""
        c = app.test_client()
        r = c.post(
            "/inscription",
            data={"pseudo": "x", "email": "", "mot_de_passe": "abcdef12"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"invalide", r.data.lower())

    def test_03_modifier_utilisateur(self):
        """Modifier le pseudo d'un utilisateur connecté."""
        c = app.test_client()
        c.post("/inscription",
               data={"pseudo": "modify_me", "email": "mod@test.fr", "mot_de_passe": "abcdef12"})
        r = c.post(
            "/profil",
            data={"action": "update", "pseudo": "modified", "email": "mod@test.fr"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"jour", r.data)  # "Profil mis à jour"

    def test_04_supprimer_utilisateur(self):
        """Suppression de compte avec confirmation explicite."""
        c = app.test_client()
        c.post("/inscription",
               data={"pseudo": "todelete", "email": "del@test.fr", "mot_de_passe": "abcdef12"})
        # Sans la bonne confirmation → refus
        r1 = c.post("/profil/supprimer",
                    data={"confirmation": "non"}, follow_redirects=True)
        self.assertIn(b"incorrect", r1.data.lower())
        # Avec confirmation explicite → OK
        r2 = c.post("/profil/supprimer",
                    data={"confirmation": "SUPPRIMER"}, follow_redirects=True)
        self.assertIn(b"supprim", r2.data.lower())
        self.assertIsNone(models.get_user_by_email("del@test.fr"))

    def test_05_lister_utilisateurs_admin(self):
        """L'admin voit la liste paginée des utilisateurs."""
        models.create_user("admin_test", "admin@test.fr", "admin1234", role="admin")
        c = app.test_client()
        c.post("/connexion",
               data={"email": "admin@test.fr", "mot_de_passe": "admin1234"})
        r = c.get("/admin")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Utilisateurs", r.data)

    def test_06_creer_service(self):
        """Création d'un service par un utilisateur connecté."""
        c = app.test_client()
        c.post("/inscription",
               data={"pseudo": "u_serv", "email": "us@test.fr", "mot_de_passe": "abcdef12"})
        cats = models.list_categories()
        r = c.post(
            "/services/ajouter",
            data={"nom": "Mon LinkedIn", "categorie_id": cats[0]["id"], "statut": "actif"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"LinkedIn", r.data)

    def test_07_connexion_identifiants_valides(self):
        """Connexion correcte → redirection vers le dashboard."""
        models.create_user("login_ok", "lok@test.fr", "abcdef12")
        r = self.client.post(
            "/connexion",
            data={"email": "lok@test.fr", "mot_de_passe": "abcdef12"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        # Le pseudo apparaît sur le tableau de bord
        self.assertIn(b"login_ok", r.data)

    def test_08_connexion_mauvais_mdp(self):
        """Connexion avec mauvais mot de passe → message d'erreur."""
        models.create_user("login_ko", "lko@test.fr", "abcdef12")
        r = self.client.post(
            "/connexion",
            data={"email": "lko@test.fr", "mot_de_passe": "wrong_pwd"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"incorrect", r.data.lower())

    def test_09_acces_page_protegee_sans_connexion(self):
        """Tentative d'accès au dashboard sans session → redirection."""
        r = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/connexion", r.headers["Location"])

    # --------------------------------------------------------
    # Tests de sécurité (Phase 6.3 du sujet)
    # --------------------------------------------------------

    def test_10_mots_de_passe_hashes_en_bdd(self):
        """Aucun mot de passe stocké en clair."""
        models.create_user("pwd_user", "pwd@test.fr", "MotDePasseClair123")
        with models.get_db() as conn:
            row = conn.execute(
                "SELECT mot_de_passe_hash FROM users WHERE email = ?",
                ("pwd@test.fr",),
            ).fetchone()
        self.assertNotIn("MotDePasseClair123", row["mot_de_passe_hash"])
        self.assertTrue(row["mot_de_passe_hash"].startswith(("pbkdf2:", "scrypt:")))

    def test_11_injection_sql_repoussee(self):
        """Tentative d'injection SQL classique sur le login."""
        r = self.client.post(
            "/connexion",
            data={"email": "' OR 1=1 --", "mot_de_passe": "x"},
            follow_redirects=True,
        )
        self.assertIn(b"incorrect", r.data.lower())
        # Personne ne s'est connecté
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_12_acces_admin_par_user_normal(self):
        """Un user normal ne peut pas atteindre /admin."""
        models.create_user("notadmin", "na@test.fr", "abcdef12", role="user")
        c = app.test_client()
        c.post("/connexion",
               data={"email": "na@test.fr", "mot_de_passe": "abcdef12"})
        r = c.get("/admin")
        self.assertEqual(r.status_code, 403)

    # --------------------------------------------------------
    # Tests export CSV
    # --------------------------------------------------------

    def test_13_export_profil_csv(self):
        """Un utilisateur connecté peut exporter ses données en CSV."""
        c = app.test_client()
        c.post("/inscription",
               data={"pseudo": "csv_user", "email": "csv@test.fr",
                      "mot_de_passe": "abcdef12"})
        cats = models.list_categories()
        c.post("/services/ajouter",
               data={"nom": "MonService", "categorie_id": cats[0]["id"],
                      "statut": "actif"})
        r = c.get("/profil/exporter")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)
        self.assertIn(b"csv_user", r.data)
        self.assertIn(b"MonService", r.data)
        self.assertIn(b"Score", r.data)

    def test_14_export_admin_csv(self):
        """L'admin peut exporter tous les utilisateurs en CSV."""
        # admin@test.fr créé dans test_05
        c = app.test_client()
        c.post("/connexion",
               data={"email": "admin@test.fr", "mot_de_passe": "admin1234"})
        r = c.get("/admin/exporter")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)

    def test_15_export_sans_connexion(self):
        """Export sans session → redirection vers la connexion."""
        r = self.client.get("/profil/exporter", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/connexion", r.headers["Location"])

    # --------------------------------------------------------
    # Tests conseils personnalisés
    # --------------------------------------------------------

    def test_16_conseils_affiches_sur_dashboard(self):
        """Le dashboard affiche un encart de conseils personnalisés."""
        c = app.test_client()
        c.post("/inscription",
               data={"pseudo": "tip_user", "email": "tip@test.fr",
                      "mot_de_passe": "abcdef12"})
        cats = models.list_categories()
        c.post("/services/ajouter",
               data={"nom": "Netflix", "categorie_id": cats[0]["id"],
                      "statut": "actif"})
        r = c.get("/dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Conseils", r.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
