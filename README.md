# Poids Mort Numérique

> *L'assistant de sobriété numérique personnelle.*

Site web éco-conçu d'inventaire et de nettoyage de son empreinte numérique.
Mini-projet TI616 « Numérique Durable » — EFREI Paris, 2025-2026.

## 1. Description

Poids Mort Numérique permet à chaque utilisateur de lister ses services en ligne
(comptes, abonnements, espaces cloud, newsletters) et de suivre la progression de
leur nettoyage via un **score de sobriété** qui augmente à mesure que les services
inutilisés passent en statut *dormant* puis *supprimé*. Une estimation
de l'énergie évitée (kWh/an) et du CO₂ évité (g/an) accompagne le score pour
rendre la démarche concrète.

Le site lui-même est conçu pour incarner les principes qu'il promeut : aucun
framework front-end, aucune police externe, aucun média décoratif, base de données
fichier, requêtes minimales.

**URL de déploiement** : *(à compléter le jour du déploiement, ex. https://poids-mort-numerique.onrender.com)*

## 2. Membres de l'équipe

| Membre               | Rôle principal                            |
| -------------------- | ----------------------------------------- |
| Antoine Poirier      | Back-end Flask, modélisation BDD          |
| Noé Millereux        | Front-end, templates Jinja2, CSS sobre    |
| Guillaume Ortells    | Authentification, admin, tests            |
| *(coordinateur)*     | Yvan Guifo — encadrement                  |

## 3. Stack technique et justification Green IT

| Couche       | Technologie                | Pourquoi                                                                    |
| ------------ | -------------------------- | --------------------------------------------------------------------------- |
| Front-end    | HTML5 + CSS3 + JS minimal  | Zéro framework, zéro build, zéro bundle. Page < 30 Ko.                      |
| Polices      | `system-ui`, `sans-serif`  | Aucune police externe : zéro requête réseau supplémentaire.                 |
| Back-end     | Flask 3 (Python)           | Micro-framework de ~1 Mo, pas de dépendance cachée.                         |
| ORM          | *aucun*                    | `sqlite3` natif. Évite ~200 Mo de dépendances (SQLAlchemy + tooling).       |
| BDD          | SQLite                     | Fichier unique, zéro serveur, zéro réseau.                                  |
| Sécurité     | Werkzeug (inclus)          | Hashage pbkdf2-sha256 des mots de passe.                                    |
| Production   | Gunicorn                   | 1 seule dépendance, processus Unix léger.                                   |

**Pourquoi pas React / Vue ?** Un framework JS impose un bundler (Webpack/Vite)
et génère un bundle de 100+ Ko avant code utile. Pour cette interface (formulaires,
listes, barres de progression CSS), le rendu serveur Jinja2 suffit.

**Pourquoi pas PostgreSQL / MySQL ?** Ces SGBD imposent un serveur dédié et
consomment de la mémoire en permanence. SQLite gère sans peine quelques milliers
de lignes, ne tourne pas au repos et ne nécessite aucune configuration réseau.

## 4. Installation et lancement local

### Prérequis
- Python 3.10+
- pip

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/Itohax78/poids-mort-numerique.git
cd poids-mort-numerique

# 2. Créer l'environnement virtuel et installer les dépendances
python -m venv venv
source venv/bin/activate         # sous Windows : venv\Scripts\activate
pip install -r requirements.txt

# 3. Configurer la clé secrète
cp .env.example .env
# Éditer .env et définir FLASK_SECRET_KEY (32+ caractères aléatoires)

# 4. (Optionnel) Initialiser des données de démonstration
python -m database.seed

# 5. Lancer en mode développement
python -m app.app
# ou : flask --app app.app run

# Accès : http://127.0.0.1:5000
```

### Comptes de démonstration (après `seed.py`)
- Admin : `admin@example.com` / `admin1234`
- User  : `alice@example.com` / `alice1234`
- User  : `bob@example.com`   / `bob1234`

### Lancement en production (exemple Gunicorn)

```bash
export FLASK_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export FLASK_ENV=production
gunicorn -w 2 -b 0.0.0.0:8000 app.app:app
```

## 5. Structure du dépôt

```
poids-mort-numerique/
├── app/
│   ├── __init__.py
│   ├── app.py                # Factory Flask
│   ├── models.py             # Accès BDD (sqlite3 natif)
│   ├── routes.py             # Routes / contrôleurs (Blueprint)
│   ├── static/
│   │   └── css/
│   │       └── style.css     # Feuille unique (~4 Ko)
│   └── templates/            # Templates Jinja2
│       ├── base.html
│       ├── home.html
│       ├── login.html
│       ├── register.html
│       ├── profile.html
│       ├── dashboard.html
│       ├── service_form.html
│       ├── admin.html
│       └── error.html
├── database/
│   ├── schema.sql            # Schéma + catégories pré-remplies
│   └── seed.py               # Script de données de démo
├── docs/
│   ├── livrable1.pdf         # Cadrage et conception (Partie 1)
│   ├── rapport.pdf           # Rapport final (Partie 2)
│   ├── diagrammes/           # UML (cas d'utilisation, classes, séquence)
│   ├── wireframes/           # Maquettes basse fidélité
│   └── eco-mesures/          # Captures EcoIndex / Lighthouse / Website Carbon
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 6. Conventions de commit

Format inspiré de Conventional Commits, en français pour la lisibilité :

```
feat(auth)    : ajout du formulaire d'inscription
fix(services) : correction du calcul du score quand 0 service
docs(readme)  : mise à jour de la section installation
refactor(db)  : extraction de la logique de stats
test(scenarios): ajout du scénario de connexion KO
```

Chaque PR fait référence à au moins une issue GitHub et est relue par un autre
membre de l'équipe avant merge dans `dev`.

## 7. Workflow Git

- `main` : branche stable, protégée, déployée.
- `dev` : branche d'intégration ; tout y est mergé avant `main`.
- `feature/*` : une branche par fonctionnalité (auth, user-crud, service-crud,
  dashboard, homepage, admin).

Les Pull Requests sont obligatoires vers `dev` ; au moins un autre membre
doit valider. Les périodiques merges `dev → main` correspondent aux versions
stables.

## 8. Documentation et rapport

- Cadrage et conception : `docs/livrable1.pdf` (Partie 1)
- Rapport final, mesures et analyse : `docs/rapport.pdf` (Partie 2)
- Diagrammes et wireframes : `docs/diagrammes/` et `docs/wireframes/`

## 9. Licence

Projet académique — usage pédagogique. Voir le rapport pour les sources
externes utilisées (référentiels GR491, ADEME, Collectif GreenIT).
