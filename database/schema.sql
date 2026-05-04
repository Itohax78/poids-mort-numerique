-- ============================================================
-- Poids Mort Numérique - Schéma de base de données
-- ============================================================
-- Conçu en cohérence avec le Livrable 1 : 3 tables minimales,
-- aucun champ superflu, index uniquement sur les colonnes
-- réellement interrogées (Green IT : moins d'index = moins
-- d'écritures, moins d'espace disque, moins d'énergie).
-- ============================================================

PRAGMA foreign_keys = ON;

-- Table des catégories de services numériques.
-- Pré-remplie : évite la saisie libre par l'utilisateur, donc
-- élimine les doublons et limite le volume de données stockées.
CREATE TABLE IF NOT EXISTS categories (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    nom                   TEXT NOT NULL UNIQUE,
    impact_kwh_an         REAL NOT NULL  -- estimation d'impact énergétique annuel (kWh)
);

-- Table des utilisateurs.
-- Volontairement minimaliste : pas de prénom, pas de nom, pas
-- de téléphone, pas de photo. Le pseudo suffit à l'identification.
CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudo                TEXT NOT NULL UNIQUE,
    email                 TEXT NOT NULL UNIQUE,
    mot_de_passe_hash     TEXT NOT NULL,
    role                  TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    date_inscription      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table des services numériques de chaque utilisateur.
-- Statut : actif → dormant → supprime (cycle de vie du nettoyage).
CREATE TABLE IF NOT EXISTS services (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    nom                      TEXT NOT NULL,
    statut                   TEXT NOT NULL DEFAULT 'actif'
                                 CHECK (statut IN ('actif', 'dormant', 'supprime')),
    date_ajout               TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_derniere_utilisation TEXT,
    user_id                  INTEGER NOT NULL,
    categorie_id             INTEGER NOT NULL,
    FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
    FOREIGN KEY (categorie_id) REFERENCES categories(id) ON DELETE RESTRICT
);

-- Index uniquement sur les colonnes réellement utilisées dans les
-- WHERE et JOIN du code (services.user_id, services.statut).
-- Aucun index "au cas où" : chaque index a un coût en écriture.
CREATE INDEX IF NOT EXISTS idx_services_user   ON services(user_id);
CREATE INDEX IF NOT EXISTS idx_services_statut ON services(statut);

-- ============================================================
-- Données initiales : catégories prédéfinies
-- Source des estimations : ordres de grandeur ADEME / GreenIT.fr
-- (valeurs conservatrices et arrondies, suffisantes pour un score)
-- ============================================================
INSERT OR IGNORE INTO categories (nom, impact_kwh_an) VALUES
    ('Reseau social',  3.5),
    ('Cloud',          8.0),
    ('Streaming',     12.0),
    ('E-commerce',     2.0),
    ('Newsletter',     1.0),
    ('Autre',          2.5);
