# -*- coding: utf-8 -*-
# Module d'acces a la base de donnees (prototype SQLite).
# ATTENTION : sur Streamlit Cloud, le systeme de fichiers est ephemere.
# Les donnees seront perdues lors des redeploiements ou des redemarrages
# apres une longue periode d'inactivite. Pour une vraie persistance en
# production, il faudra migrer vers une base externe (ex: Supabase).

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artisans.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS artisans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            nom_entreprise TEXT,
            telephone TEXT,
            ville_base TEXT,
            rayon_km INTEGER DEFAULT 20,
            zones_desservies TEXT,
            corps_metier TEXT,
            description TEXT,
            photos TEXT,
            date_creation TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS indisponibilites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artisan_id INTEGER NOT NULL,
            date_indispo TEXT NOT NULL,
            UNIQUE(artisan_id, date_indispo),
            FOREIGN KEY (artisan_id) REFERENCES artisans(id)
        )
    """)

    # Migration douce : si la table "artisans" existait deja sans la colonne
    # rayon_km (ancienne version du prototype), on l'ajoute sans rien casser.
    try:
        cur.execute("ALTER TABLE artisans ADD COLUMN rayon_km INTEGER DEFAULT 20")
    except sqlite3.OperationalError:
        pass  # la colonne existe deja

    conn.commit()
    conn.close()


def get_artisan_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM artisans WHERE email = ?", (email.strip().lower(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_artisan_by_id(artisan_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM artisans WHERE id = ?", (artisan_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_artisan(email, nom_entreprise, telephone, ville_base, rayon_km,
                    corps_metier_list, description, photos_paths):
    """Cree la fiche artisan si elle n'existe pas, sinon la met a jour.
    ville_base = ville de reference du secteur d'intervention.
    rayon_km = rayon d'intervention en kilometres autour de cette ville."""
    conn = get_connection()
    cur = conn.cursor()
    email = email.strip().lower()
    corps_metier_str = ",".join(corps_metier_list)
    photos_str = ",".join(photos_paths)

    cur.execute("SELECT id FROM artisans WHERE email = ?", (email,))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE artisans
            SET nom_entreprise=?, telephone=?, ville_base=?, rayon_km=?,
                corps_metier=?, description=?, photos=?
            WHERE email=?
        """, (nom_entreprise, telephone, ville_base, rayon_km,
              corps_metier_str, description, photos_str, email))
        artisan_id = existing["id"]
    else:
        cur.execute("""
            INSERT INTO artisans
                (email, nom_entreprise, telephone, ville_base, rayon_km,
                 corps_metier, description, photos, date_creation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, nom_entreprise, telephone, ville_base, rayon_km,
              corps_metier_str, description, photos_str, datetime.now().isoformat()))
        artisan_id = cur.lastrowid

    conn.commit()
    conn.close()
    return artisan_id


def get_indisponibilites(artisan_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT date_indispo FROM indisponibilites WHERE artisan_id = ? ORDER BY date_indispo",
        (artisan_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [r["date_indispo"] for r in rows]


def set_indisponibilites(artisan_id, dates_list):
    """Remplace entierement la liste des indisponibilites de l'artisan.
    dates_list : liste de chaines au format 'YYYY-MM-DD'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM indisponibilites WHERE artisan_id = ?", (artisan_id,))
    for d in dates_list:
        cur.execute(
            "INSERT OR IGNORE INTO indisponibilites (artisan_id, date_indispo) VALUES (?, ?)",
            (artisan_id, d)
        )
    conn.commit()
    conn.close()


def get_all_artisans():
    """Retourne toutes les fiches artisans (utile plus tard pour le matching cote client)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM artisans ORDER BY date_creation DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

