"""
models.py — Couche d'accès aux données.

Choix de sobriété : aucun ORM. SQLite natif via le module
`sqlite3` de la bibliothèque standard. Cela élimine une couche
d'abstraction (et ses dépendances), réduit la consommation
mémoire et donne un contrôle direct sur chaque requête.

Toutes les requêtes utilisent des paramètres `?` (parametrized
queries) pour empêcher les injections SQL.
"""

import os
import sqlite3
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash


# Chemin du fichier de base de données. Un seul fichier, zéro
# serveur, zéro configuration réseau.
DB_PATH = os.environ.get(
    "POIDS_MORT_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "poids_mort.db"),
)
SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "database", "schema.sql"
)


# ----------------------------------------------------------------
# Initialisation et connexion
# ----------------------------------------------------------------

def init_db():
    """Crée la base et applique le schéma si elle n'existe pas."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db():
    """Context manager qui fournit une connexion et la ferme proprement."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ----------------------------------------------------------------
# Utilisateurs — CRUD complet
# ----------------------------------------------------------------

def create_user(pseudo, email, mot_de_passe, role="user"):
    """Crée un utilisateur. Retourne l'id ou None si conflit."""
    pwd_hash = generate_password_hash(mot_de_passe)
    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO users (pseudo, email, mot_de_passe_hash, role) "
                "VALUES (?, ?, ?, ?)",
                (pseudo, email, pwd_hash, role),
            )
            conn.commit()
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # pseudo ou email déjà pris


def get_user_by_id(user_id):
    """Lit les colonnes utiles uniquement (pas de SELECT *)."""
    with get_db() as conn:
        return conn.execute(
            "SELECT id, pseudo, email, role, date_inscription "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def get_user_by_email(email):
    """Récupère le hash du mot de passe pour la connexion."""
    with get_db() as conn:
        return conn.execute(
            "SELECT id, pseudo, email, mot_de_passe_hash, role "
            "FROM users WHERE email = ?",
            (email,),
        ).fetchone()


def list_users(limit=20, offset=0):
    """Liste paginée. LIMIT/OFFSET imposés pour Green IT."""
    with get_db() as conn:
        return conn.execute(
            "SELECT u.id, u.pseudo, u.email, u.role, u.date_inscription, "
            "       COUNT(s.id) AS nb_services "
            "FROM users u "
            "LEFT JOIN services s ON s.user_id = u.id "
            "GROUP BY u.id "
            "ORDER BY u.date_inscription DESC "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def count_users():
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def update_user(user_id, pseudo, email):
    """Mise à jour minimale : seuls pseudo et email peuvent changer."""
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET pseudo = ?, email = ? WHERE id = ?",
                (pseudo, email, user_id),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def update_user_password(user_id, nouveau_mot_de_passe):
    pwd_hash = generate_password_hash(nouveau_mot_de_passe)
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET mot_de_passe_hash = ? WHERE id = ?",
            (pwd_hash, user_id),
        )
        conn.commit()


def delete_user(user_id):
    """La cascade FK supprime aussi les services liés."""
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


def verify_password(user_row, mot_de_passe):
    return check_password_hash(user_row["mot_de_passe_hash"], mot_de_passe)


# ----------------------------------------------------------------
# Catégories
# ----------------------------------------------------------------

def list_categories():
    with get_db() as conn:
        return conn.execute(
            "SELECT id, nom, impact_kwh_an FROM categories ORDER BY nom"
        ).fetchall()


def get_category(cat_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, nom, impact_kwh_an FROM categories WHERE id = ?",
            (cat_id,),
        ).fetchone()


# ----------------------------------------------------------------
# Services numériques — CRUD complet
# ----------------------------------------------------------------

def create_service(user_id, nom, categorie_id, statut="actif"):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO services (nom, statut, user_id, categorie_id) "
            "VALUES (?, ?, ?, ?)",
            (nom, statut, user_id, categorie_id),
        )
        conn.commit()
        return cur.lastrowid


def get_service(service_id, user_id=None):
    """Si user_id est fourni, on vérifie que le service lui appartient."""
    sql = (
        "SELECT s.id, s.nom, s.statut, s.date_ajout, s.user_id, "
        "       s.categorie_id, c.nom AS categorie_nom, c.impact_kwh_an "
        "FROM services s JOIN categories c ON c.id = s.categorie_id "
        "WHERE s.id = ?"
    )
    params = [service_id]
    if user_id is not None:
        sql += " AND s.user_id = ?"
        params.append(user_id)
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()


def list_services_for_user(user_id, statut=None, limit=20, offset=0, order_by="date_desc"):
    """Liste paginée des services d'un utilisateur, filtrable par statut et triée."""
    sql = (
        "SELECT s.id, s.nom, s.statut, s.date_ajout, "
        "       c.nom AS categorie_nom, c.impact_kwh_an, "
        "       (s.statut = 'actif' AND (julianday('now') - julianday(s.date_ajout)) > 180) AS is_zombie "
        "FROM services s JOIN categories c ON c.id = s.categorie_id "
        "WHERE s.user_id = ?"
    )
    params = [user_id]
    if statut:
        sql += " AND s.statut = ?"
        params.append(statut)
        
    if order_by == "date_asc":
        sql += " ORDER BY s.date_ajout ASC"
    elif order_by == "nom":
        sql += " ORDER BY s.nom ASC"
    elif order_by == "categorie":
        sql += " ORDER BY c.nom ASC, s.nom ASC"
    elif order_by == "statut":
        sql += " ORDER BY s.statut ASC, s.date_ajout DESC"
    else:
        sql += " ORDER BY s.date_ajout DESC"
        
    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_db() as conn:
        return conn.execute(sql, params).fetchall()


def count_services_for_user(user_id, statut=None):
    sql = "SELECT COUNT(*) AS n FROM services WHERE user_id = ?"
    params = [user_id]
    if statut:
        sql += " AND statut = ?"
        params.append(statut)
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()["n"]


def update_service(service_id, user_id, nom, categorie_id, statut):
    with get_db() as conn:
        conn.execute(
            "UPDATE services SET nom = ?, categorie_id = ?, statut = ? "
            "WHERE id = ? AND user_id = ?",
            (nom, categorie_id, statut, service_id, user_id),
        )
        conn.commit()


def change_service_status(service_id, user_id, nouveau_statut):
    with get_db() as conn:
        conn.execute(
            "UPDATE services SET statut = ? WHERE id = ? AND user_id = ?",
            (nouveau_statut, service_id, user_id),
        )
        conn.commit()


def delete_service(service_id, user_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM services WHERE id = ? AND user_id = ?",
            (service_id, user_id),
        )
        conn.commit()


# ----------------------------------------------------------------
# Score de sobriété et statistiques
# ----------------------------------------------------------------

def get_user_stats(user_id):
    """
    Calcule en une seule requête le récap par statut + l'impact
    cumulé. Retourne un dict prêt à afficher.

    Score de sobriété (0 à 100) :
      - 0   service ajouté            → 100 (rien à nettoyer)
      - X services tous actifs        → score bas
      - Y services supprimés sur N    → score = 100 * Y / N (arrondi)

    Logique : on récompense la part de services nettoyés (dormant
    compte pour 0,5 ; supprime pour 1).
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT s.statut, COUNT(*) AS n, "
            "       COALESCE(SUM(c.impact_kwh_an), 0) AS impact "
            "FROM services s JOIN categories c ON c.id = s.categorie_id "
            "WHERE s.user_id = ? "
            "GROUP BY s.statut",
            (user_id,),
        ).fetchall()

    par_statut = {"actif": 0, "dormant": 0, "supprime": 0}
    impact_par_statut = {"actif": 0.0, "dormant": 0.0, "supprime": 0.0}
    for r in rows:
        par_statut[r["statut"]] = r["n"]
        impact_par_statut[r["statut"]] = float(r["impact"])

    total = sum(par_statut.values())
    if total == 0:
        score = 100
    else:
        nettoyes = par_statut["dormant"] * 0.5 + par_statut["supprime"] * 1.0
        score = round(100 * nettoyes / total)

    # Estimation d'énergie évitée : impact des services supprimés +
    # 50 % de celui des dormants (un service dormant continue à
    # consommer un peu mais beaucoup moins qu'un actif).
    kwh_evites = impact_par_statut["supprime"] + 0.5 * impact_par_statut["dormant"]
    # Facteur d'émission moyen électricité France ~50 g CO2 / kWh
    co2_evite_g = round(kwh_evites * 50)

    return {
        "total": total,
        "actifs": par_statut["actif"],
        "dormants": par_statut["dormant"],
        "supprimes": par_statut["supprime"],
        "score": score,
        "kwh_evites": round(kwh_evites, 1),
        "co2_evite_g": co2_evite_g,
    }


def get_global_stats():
    """Statistiques globales pour l'admin."""
    with get_db() as conn:
        nb_users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        nb_services = conn.execute(
            "SELECT statut, COUNT(*) AS n FROM services GROUP BY statut"
        ).fetchall()
    par_statut = {"actif": 0, "dormant": 0, "supprime": 0}
    for r in nb_services:
        par_statut[r["statut"]] = r["n"]
    return {
        "nb_users": nb_users,
        "nb_actifs": par_statut["actif"],
        "nb_dormants": par_statut["dormant"],
        "nb_supprimes": par_statut["supprime"],
        "nb_total": sum(par_statut.values()),
    }


# ----------------------------------------------------------------
# Export CSV
# ----------------------------------------------------------------

def export_services_for_user(user_id):
    """Tous les services d'un utilisateur, sans pagination (export)."""
    with get_db() as conn:
        return conn.execute(
            "SELECT s.nom, s.statut, s.date_ajout, "
            "       s.date_derniere_utilisation, "
            "       c.nom AS categorie_nom, c.impact_kwh_an "
            "FROM services s JOIN categories c ON c.id = s.categorie_id "
            "WHERE s.user_id = ? "
            "ORDER BY s.date_ajout DESC",
            (user_id,),
        ).fetchall()


def export_all_users_with_services():
    """Export admin : tous les utilisateurs et leurs services (1 requête)."""
    with get_db() as conn:
        return conn.execute(
            "SELECT u.pseudo, u.email, u.role, u.date_inscription, "
            "       s.nom AS service_nom, s.statut AS service_statut, "
            "       s.date_ajout AS service_date_ajout, "
            "       s.date_derniere_utilisation, "
            "       c.nom AS categorie_nom, c.impact_kwh_an "
            "FROM users u "
            "LEFT JOIN services s ON s.user_id = u.id "
            "LEFT JOIN categories c ON c.id = s.categorie_id "
            "ORDER BY u.pseudo, s.date_ajout DESC"
        ).fetchall()
