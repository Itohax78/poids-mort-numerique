"""
routes.py — Routage et logique applicative.

Organisation : un seul Blueprint Flask. Pour ce périmètre
(quelques pages), un découpage en plusieurs blueprints
ajouterait de la complexité sans bénéfice.

Sécurité :
  - Toutes les routes sensibles utilisent @login_required ou
    @admin_required.
  - Les requêtes BDD sont paramétrées (cf. models.py).
  - Les mots de passe sont hashés via werkzeug (pbkdf2-sha256).
  - Sessions Flask signées (clé secrète obligatoire).
"""

import csv
import io
from datetime import date
from functools import wraps

from flask import (
    Blueprint, Response, render_template, request, redirect, url_for,
    session, flash, abort
)

from . import models


bp = Blueprint("main", __name__)


# ----------------------------------------------------------------
# Décorateurs d'autorisation
# ----------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "error")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ----------------------------------------------------------------
# Validation simple des entrées
# ----------------------------------------------------------------

def _valid_email(email):
    return email and "@" in email and "." in email.split("@")[-1] and len(email) <= 120


def _valid_pseudo(pseudo):
    return pseudo and 2 <= len(pseudo) <= 40 and pseudo.replace("_", "").replace("-", "").isalnum()


# ----------------------------------------------------------------
# Pages publiques
# ----------------------------------------------------------------

@bp.route("/")
def home():
    stats = models.get_global_stats()
    # Calcul des kg CO2 evités globalement (approximatif)
    co2_total_kg = round(stats.get("nb_supprimes", 0) * 1.5 + stats.get("nb_dormants", 0) * 0.5) 
    
    # Mur de la honte (statistiques anonymisées)
    mur_honte = {}
    with models.get_db() as conn:
        # Pire Zombie : Le nom de service le plus souvent déclaré (statut actif)
        pire_zombie = conn.execute(
            "SELECT nom, COUNT(*) as count FROM services WHERE statut = 'actif' GROUP BY nom ORDER BY count DESC LIMIT 1"
        ).fetchone()
        mur_honte['pire_zombie'] = pire_zombie['nom'] if pire_zombie else "Aucun"
        
        # Le plus vieux compte supprimé (différence entre date actuelle et date_ajout)
        vieux_supprime = conn.execute(
            "SELECT nom, CAST(julianday('now') - julianday(date_ajout) AS INTEGER) as age_jours FROM services WHERE statut = 'supprime' ORDER BY age_jours DESC LIMIT 1"
        ).fetchone()
        mur_honte['vieux_supprime'] = vieux_supprime
        
    return render_template("home.html", stats=stats, co2_total_kg=co2_total_kg, mur_honte=mur_honte)


# ----------------------------------------------------------------
# Authentification
# ----------------------------------------------------------------

@bp.route("/inscription", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        pseudo = request.form.get("pseudo", "").strip()
        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")

        if not _valid_pseudo(pseudo):
            flash("Pseudo invalide (2 à 40 caractères, alphanumériques).", "error")
        elif not _valid_email(email):
            flash("Email invalide.", "error")
        elif len(mot_de_passe) < 8:
            flash("Le mot de passe doit faire au moins 8 caractères.", "error")
        else:
            user_id = models.create_user(pseudo, email, mot_de_passe)
            if user_id is None:
                flash("Ce pseudo ou cet email est déjà pris.", "error")
            else:
                session.clear()
                session["user_id"] = user_id
                session["pseudo"] = pseudo
                session["role"] = "user"
                flash("Compte créé avec succès.", "success")
                return redirect(url_for("main.dashboard"))
    return render_template("register.html")


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        mot_de_passe = request.form.get("mot_de_passe", "")
        user = models.get_user_by_email(email)
        if user is None or not models.verify_password(user, mot_de_passe):
            # Message volontairement non discriminant (sécurité)
            flash("Identifiants incorrects.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["pseudo"] = user["pseudo"]
            session["role"] = user["role"]
            return redirect(url_for("main.dashboard"))
    return render_template("login.html")


@bp.route("/deconnexion", methods=["POST"])
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for("main.home"))


# ----------------------------------------------------------------
# Profil utilisateur — CRUD
# ----------------------------------------------------------------

@bp.route("/profil", methods=["GET", "POST"])
@login_required
def profile():
    user = models.get_user_by_id(session["user_id"])
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update":
            pseudo = request.form.get("pseudo", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not _valid_pseudo(pseudo) or not _valid_email(email):
                flash("Données invalides.", "error")
            elif models.update_user(user["id"], pseudo, email):
                session["pseudo"] = pseudo
                flash("Profil mis à jour.", "success")
                return redirect(url_for("main.profile"))
            else:
                flash("Pseudo ou email déjà utilisé.", "error")
        elif action == "password":
            actuel = request.form.get("mot_de_passe_actuel", "")
            nouveau = request.form.get("nouveau_mot_de_passe", "")
            user_full = models.get_user_by_email(user["email"])
            if not models.verify_password(user_full, actuel):
                flash("Mot de passe actuel incorrect.", "error")
            elif len(nouveau) < 8:
                flash("Nouveau mot de passe trop court (8 caractères min).", "error")
            else:
                models.update_user_password(user["id"], nouveau)
                flash("Mot de passe modifié.", "success")
                return redirect(url_for("main.profile"))
    return render_template("profile.html", user=user)


@bp.route("/profil/supprimer", methods=["POST"])
@login_required
def delete_account():
    """Suppression de compte avec confirmation explicite par formulaire."""
    confirm = request.form.get("confirmation", "")
    if confirm != "SUPPRIMER":
        flash("Confirmation incorrecte. Tapez SUPPRIMER pour confirmer.", "error")
        return redirect(url_for("main.profile"))
    models.delete_user(session["user_id"])
    session.clear()
    flash("Votre compte a été supprimé.", "success")
    return redirect(url_for("main.home"))


@bp.route("/profil/exporter")
@login_required
def export_profile():
    """Export CSV des données personnelles (portabilité RGPD)."""
    user_id = session["user_id"]
    user = models.get_user_by_id(user_id)
    stats = models.get_user_stats(user_id)
    services = models.export_services_for_user(user_id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Pseudo", "Email", "Date inscription",
        "Service", "Catégorie", "Statut", "Date ajout",
        "Dernière utilisation",
        "Score sobriété", "Impact évité (kWh)", "CO2 évité (g)",
    ])

    common = [user["pseudo"], user["email"], user["date_inscription"]]
    stat_cols = [stats["score"], stats["kwh_evites"], stats["co2_evite_g"]]

    if services:
        for s in services:
            writer.writerow(common + [
                s["nom"], s["categorie_nom"], s["statut"],
                s["date_ajout"], s["date_derniere_utilisation"] or "",
            ] + stat_cols)
    else:
        writer.writerow(common + ["", "", "", "", ""] + stat_cols)

    filename = f"poids_mort_{user['pseudo']}_{date.today().isoformat()}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----------------------------------------------------------------
# Conseils personnalisés (zéro requ��te BDD supplémentaire)
# ----------------------------------------------------------------

_TIPS_GENERIQUES = [
    "Désabonnez-vous des newsletters que vous ne lisez plus.",
    "Supprimez vos comptes sur les sites que vous n'utilisez plus.",
    "Préférez le Wi-Fi aux données mobiles (4× moins énergivore).",
    "Videz régulièrement votre boîte mail et vos fichiers cloud inutiles.",
]


def _generate_conseils(stats, services):
    """Retourne une liste de conseils basés sur les stats et services."""
    conseils = []

    if stats["total"] == 0:
        conseils.append(
            "Commencez par ajouter vos services numériques pour "
            "évaluer votre empreinte."
        )
        return conseils

    if stats["score"] >= 80:
        conseils.append(
            f"Bravo ! Votre score de {stats['score']}/100 est excellent. "
            "Continuez à garder vos services sous contrôle."
        )
    elif stats["score"] < 30 and stats["actifs"] > 0:
        conseils.append(
            f"Votre score est de {stats['score']}/100. Passez en revue "
            f"vos {stats['actifs']} service(s) actif(s) : certains sont "
            "peut-être devenus inutiles."
        )

    if stats["dormants"] > 0:
        conseils.append(
            f"Vous avez {stats['dormants']} service(s) dormant(s). "
            "Supprimez-les pour améliorer votre score et réduire "
            "votre empreinte."
        )

    # Détecte la catégorie la plus énergivore parmi les services actifs
    impact_par_cat = {}
    for s in services:
        if s["statut"] == "actif":
            cat = s["categorie_nom"]
            impact_par_cat[cat] = impact_par_cat.get(cat, 0) + s["impact_kwh_an"]
    if impact_par_cat:
        pire_cat = max(impact_par_cat, key=impact_par_cat.get)
        if impact_par_cat[pire_cat] >= 5:
            conseils.append(
                f"Vos services « {pire_cat} » représentent "
                f"{impact_par_cat[pire_cat]:.1f} kWh/an. C'est votre "
                "catégorie la plus énergivore."
            )

    # Ajout d'un tip générique si peu de conseils personnalisés
    if len(conseils) < 2:
        idx = stats["total"] % len(_TIPS_GENERIQUES)
        conseils.append(_TIPS_GENERIQUES[idx])

    return conseils


# ----------------------------------------------------------------
# Tableau de bord et services numériques — CRUD
# ----------------------------------------------------------------

@bp.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    statut_filter = request.args.get("statut") or None
    if statut_filter not in (None, "actif", "dormant", "supprime"):
        statut_filter = None
    
    sort_filter = request.args.get("sort", "date_desc")
        
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset = (page - 1) * per_page

    services = models.list_services_for_user(
        user_id, statut=statut_filter, limit=per_page, offset=offset, order_by=sort_filter
    )
    nb_total = models.count_services_for_user(user_id, statut=statut_filter)
    stats = models.get_user_stats(user_id)
    conseils = _generate_conseils(stats, services)

    template = "cimetiere.html" if statut_filter == "supprime" else "dashboard.html"

    return render_template(
        template,
        services=services,
        stats=stats,
        conseils=conseils,
        statut_filter=statut_filter,
        sort_filter=sort_filter,
        page=page,
        per_page=per_page,
        nb_total=nb_total,
    )


@bp.route("/services/ajouter", methods=["GET", "POST"])
@login_required
def add_service():
    categories = models.list_categories()
    if request.method == "POST":
        noms_bruts = request.form.get("nom", "").strip()
        try:
            categorie_id = int(request.form.get("categorie_id", "0"))
        except ValueError:
            categorie_id = 0
        statut = request.form.get("statut", "actif")
        
        noms_liste = [n.strip() for n in noms_bruts.split('\n') if n.strip()]
        
        if not noms_liste:
            flash("Veuillez renseigner au moins un nom.", "error")
        elif any(len(n) > 80 for n in noms_liste):
            flash("Chaque nom doit faire moins de 80 caractères.", "error")
        elif models.get_category(categorie_id) is None:
            flash("Catégorie invalide.", "error")
        elif statut not in ("actif", "dormant", "supprime"):
            flash("Statut invalide.", "error")
        else:
            for nom in noms_liste:
                models.create_service(session["user_id"], nom, categorie_id, statut)
            if len(noms_liste) > 1:
                flash(f"{len(noms_liste)} services ajoutés.", "success")
            else:
                flash("Service ajouté.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("service_form.html", categories=categories, service=None)


@bp.route("/services/<int:service_id>/modifier", methods=["GET", "POST"])
@login_required
def edit_service(service_id):
    service = models.get_service(service_id, user_id=session["user_id"])
    if service is None:
        abort(404)
    categories = models.list_categories()
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        try:
            categorie_id = int(request.form.get("categorie_id", "0"))
        except ValueError:
            categorie_id = 0
        statut = request.form.get("statut", "actif")
        if not nom or len(nom) > 80:
            flash("Nom invalide.", "error")
        elif models.get_category(categorie_id) is None:
            flash("Catégorie invalide.", "error")
        elif statut not in ("actif", "dormant", "supprime"):
            flash("Statut invalide.", "error")
        else:
            models.update_service(service_id, session["user_id"], nom, categorie_id, statut)
            flash("Service mis à jour.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("service_form.html", categories=categories, service=service)


@bp.route("/services/<int:service_id>/statut", methods=["POST"])
@login_required
def change_status(service_id):
    nouveau = request.form.get("statut")
    if nouveau not in ("actif", "dormant", "supprime"):
        abort(400)
    # On vérifie l'appartenance via get_service
    if models.get_service(service_id, user_id=session["user_id"]) is None:
        abort(404)
    models.change_service_status(service_id, session["user_id"], nouveau)
    flash("Statut mis à jour.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@bp.route("/services/<int:service_id>/supprimer", methods=["POST"])
@login_required
def remove_service(service_id):
    if models.get_service(service_id, user_id=session["user_id"]) is None:
        abort(404)
    models.delete_service(service_id, session["user_id"])
    flash("Service supprimé de votre inventaire.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/services/flemme")
@login_required
def flemme():
    """Tire au sort un service actif ou dormant pour encourager le nettoyage."""
    user_id = session["user_id"]
    with models.get_db() as conn:
        service = conn.execute(
            "SELECT s.id, s.nom, s.statut, c.nom AS categorie_nom, c.impact_kwh_an "
            "FROM services s JOIN categories c ON c.id = s.categorie_id "
            "WHERE s.user_id = ? AND s.statut IN ('actif', 'dormant') "
            "ORDER BY RANDOM() LIMIT 1",
            (user_id,)
        ).fetchone()
        
    if not service:
        flash("Bravo ! Vous n'avez plus aucun service actif ou dormant à nettoyer.", "success")
        return redirect(url_for("main.dashboard"))
        
    return render_template("flemme.html", service=service)


@bp.route("/badge.svg")
def badge_svg():
    """Génère un badge SVG léger avec le score de sobriété."""
    user_id = request.args.get("u")
    if not user_id:
        abort(400)
    
    # Récupération du score
    stats = models.get_user_stats(user_id)
    score = stats.get("score", 0)
    
    # Couleurs basées sur le score
    color = "#1b4332" if score >= 80 else ("#e8c878" if score >= 50 else "#a4342e")
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="180" height="40" aria-label="Eco-Score: {score}/100">
  <rect width="100" height="40" fill="#f8f7f4" rx="4" />
  <rect x="100" width="80" height="40" fill="{color}" rx="4" />
  <text x="50" y="25" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#1a1d1c" text-anchor="middle">Eco-Score</text>
  <text x="140" y="26" font-family="system-ui, sans-serif" font-size="16" font-weight="bold" fill="#ffffff" text-anchor="middle">{score}/100</text>
</svg>'''
    return Response(svg, mimetype="image/svg+xml")


# ----------------------------------------------------------------
# Espace administrateur
# ----------------------------------------------------------------

@bp.route("/admin")
@login_required
@admin_required
def admin_home():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    offset = (page - 1) * per_page
    users = models.list_users(limit=per_page, offset=offset)
    nb_total = models.count_users()
    stats = models.get_global_stats()
    return render_template(
        "admin.html",
        users=users,
        stats=stats,
        page=page,
        per_page=per_page,
        nb_total=nb_total,
    )


@bp.route("/admin/utilisateurs/<int:user_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    if user_id == session["user_id"]:
        flash("Vous ne pouvez pas supprimer votre propre compte ici.", "error")
        return redirect(url_for("main.admin_home"))
    models.delete_user(user_id)
    flash("Utilisateur supprimé.", "success")
    return redirect(url_for("main.admin_home"))


@bp.route("/admin/exporter")
@login_required
@admin_required
def admin_export():
    """Export CSV de tous les utilisateurs et leurs services."""
    rows = models.export_all_users_with_services()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Pseudo", "Email", "Rôle", "Date inscription",
        "Service", "Catégorie", "Statut service", "Date ajout",
        "Dernière utilisation", "Impact (kWh/an)",
    ])
    for r in rows:
        writer.writerow([
            r["pseudo"], r["email"], r["role"], r["date_inscription"],
            r["service_nom"] or "", r["categorie_nom"] or "",
            r["service_statut"] or "", r["service_date_ajout"] or "",
            r["date_derniere_utilisation"] or "",
            r["impact_kwh_an"] if r["impact_kwh_an"] else "",
        ])

    filename = f"poids_mort_export_admin_{date.today().isoformat()}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----------------------------------------------------------------
# Pages d'erreur sobres (pas de stack trace exposée)
# ----------------------------------------------------------------

@bp.app_errorhandler(403)
def err_403(e):
    return render_template("error.html", code=403, message="Accès refusé."), 403


@bp.app_errorhandler(404)
def err_404(e):
    return render_template("error.html", code=404, message="Page introuvable."), 404
