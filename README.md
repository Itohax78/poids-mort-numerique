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

**URL de déploiement** : `<À COMPLÉTER>` *(ex. https://poids-mort-numerique.onrender.com — voir section 5)*

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

## 5. Déploiement (Render — free tier)

Le projet est configuré pour un déploiement *Infrastructure as Code* sur
[Render](https://render.com) via [`render.yaml`](./render.yaml). Aucune
configuration manuelle n'est nécessaire au-delà du raccordement du dépôt.

### Étapes

1. **Pousser** le dépôt sur GitHub (branche `main`).
2. Sur Render : *Dashboard → New + → Blueprint → Connect a repository*,
   sélectionner `poids-mort-numerique`. Render lit `render.yaml` et
   provisionne automatiquement un service web Python (plan **free**,
   région **Frankfurt**).
3. La variable `FLASK_SECRET_KEY` est générée par Render
   (`generateValue: true`) — aucun secret n'est committé.
4. Déploiement automatique à chaque `git push` sur `main`.
5. **URL publique** : `<À COMPLÉTER après le premier deploy>`

### Que fait le start command ?

```text
python render_init.py && gunicorn app.app:app
```

`render_init.py` détecte si la BDD SQLite existe :
si oui → ne touche à rien ; si non → lance `database/seed.py`
qui crée le schéma + un jeu de données de démo. Gunicorn prend
le relais sur le port que Render lui passe (variable `$PORT`, gérée
par défaut par Gunicorn).

### Choix assumé : SQLite + filesystem éphémère, sans disk persistant

Le plan **free** de Render ne fournit pas de *disk* persistant
(option payante à partir du plan Starter). Conséquence : à chaque
*cold-start* (après ~15 min d'inactivité, ou à chaque redéploiement),
le filesystem est recréé à zéro et la BDD SQLite repart vierge. Le
script `render_init.py` ré-applique alors le `seed` : les trois
comptes de démo (admin / alice / bob) sont toujours disponibles.

C'est un compromis **assumé**, cohérent avec la démarche Green IT
du projet :

- **Pas de serveur de BDD payant qui tourne 24/7** (Postgres managé
  consomme de la mémoire et de l'énergie en permanence, même sans
  trafic). SQLite + free tier = ressources allouées **uniquement
  pendant les requêtes**.
- **Mise en veille automatique** après inactivité : le service ne
  consomme rien tant qu'aucun visiteur ne vient. Sobriété native.
- **Contexte démo / soutenance** : la perte des données utilisateur
  entre deux sessions est sans conséquence — on évalue
  l'éco-conception, pas la persistance multi-mois.
- **Réversible** : passer en plan Starter + disk persistant ou
  brancher une vraie BDD demande uniquement quelques lignes dans
  `render.yaml` ; aucun code applicatif à modifier (le chemin BDD
  est déjà paramétrable via `POIDS_MORT_DB`).

Le coût : un cold-start initial un peu plus long (re-build + seed),
soit ~10-30 s au premier hit après inactivité. Acceptable pour une
démo, et inhérent au plan gratuit de tous les PaaS de ce type.

## 6. Structure du dépôt

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

## 7. Conventions de commit

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

## 8. Workflow Git

- `main` : branche stable, protégée, déployée.
- `dev` : branche d'intégration ; tout y est mergé avant `main`.
- `feature/*` : une branche par fonctionnalité (auth, user-crud, service-crud,
  dashboard, homepage, admin).

Les Pull Requests sont obligatoires vers `dev` ; au moins un autre membre
doit valider. Les périodiques merges `dev → main` correspondent aux versions
stables.

## 9. Documentation et rapport

- Cadrage et conception : `docs/livrable1.pdf` (Partie 1)
- Rapport final, mesures et analyse : `docs/rapport.pdf` (Partie 2)
- Diagrammes et wireframes : `docs/diagrammes/` et `docs/wireframes/`

## 10. Licence

Projet académique — usage pédagogique. Voir le rapport pour les sources
externes utilisées (référentiels GR491, ADEME, Collectif GreenIT).
