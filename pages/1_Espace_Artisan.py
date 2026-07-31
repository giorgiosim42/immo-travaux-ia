# -*- coding: utf-8 -*-
import streamlit as st
import os
import json
import re
from datetime import date, timedelta

from db import (
    init_db,
    get_artisan_by_email,
    upsert_artisan,
    get_indisponibilites,
    set_indisponibilites,
)

st.set_page_config(page_title="Espace Artisan - IA Immo", page_icon="\U0001F477", layout="wide")

init_db()

UPLOAD_DIR = "uploads_artisans"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@st.cache_data
def charger_corps_metier():
    with open("base_prix_travaux.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [cat["nom_categorie"] for cat in data["categories_travaux"]]


CORPS_METIER = charger_corps_metier()

st.title("\U0001F477 Espace Artisan")

st.warning(
    "Version prototype de demonstration : la connexion se fait uniquement par email, "
    "sans mot de passe. N'importe qui connaissant votre email pourrait modifier votre fiche. "
    "Une veritable authentification sera necessaire avant toute mise en production. "
    "Les donnees sont stockees dans une base locale (SQLite) qui peut etre reinitialisee "
    "lors des redeploiements de l'application."
)

# --- CONNEXION SIMPLE PAR EMAIL (prototype, sans mot de passe) ---
if "artisan_connecte" not in st.session_state:
    st.session_state["artisan_connecte"] = None

if not st.session_state["artisan_connecte"]:
    st.subheader("Connexion / Inscription")
    email_saisi = st.text_input("Votre adresse email professionnelle")

    if st.button("Continuer", type="primary", disabled=not email_saisi.strip()):
        email_propre = email_saisi.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_propre):
            st.error("Adresse email invalide.")
        else:
            existant = get_artisan_by_email(email_propre)
            st.session_state["artisan_connecte"] = email_propre
            if existant:
                st.success("Bienvenue de retour !")
            else:
                st.info("Aucune fiche existante pour cet email : creez votre profil ci-dessous.")
            st.rerun()

    st.stop()

email_connecte = st.session_state["artisan_connecte"]
artisan = get_artisan_by_email(email_connecte)

col_titre, col_deco = st.columns([4, 1])
with col_titre:
    st.success(f"Connecte en tant que : {email_connecte}")
with col_deco:
    if st.button("Se deconnecter"):
        st.session_state["artisan_connecte"] = None
        st.rerun()

st.markdown("---")

# --- FORMULAIRE DE PROFIL ---
st.subheader("Votre fiche artisan (visible des clients)")

with st.form("form_profil_artisan"):
    nom_entreprise = st.text_input(
        "Nom de l'entreprise / activite",
        value=(artisan.get("nom_entreprise") or "") if artisan else ""
    )
    telephone = st.text_input(
        "Telephone de contact",
        value=(artisan.get("telephone") or "") if artisan else ""
    )
    ville_base = st.text_input(
        "Ville de base",
        value=(artisan.get("ville_base") or "") if artisan else "",
        placeholder="ex : Lyon"
    )
    zones_desservies = st.text_area(
        "Zones / villes ou vous intervenez (separees par des virgules)",
        value=(artisan.get("zones_desservies") or "") if artisan else "",
        placeholder="ex : Lyon, Villeurbanne, Venissieux, Bron"
    )

    corps_metier_defaut = []
    if artisan and artisan.get("corps_metier"):
        corps_metier_defaut = [c for c in artisan["corps_metier"].split(",") if c]

    corps_metier_selectionnes = st.multiselect(
        "Corps de metier proposes",
        options=CORPS_METIER,
        default=corps_metier_defaut
    )

    description = st.text_area(
        "Presentation / texte de presentation",
        value=(artisan.get("description") or "") if artisan else "",
        placeholder="Decrivez votre savoir-faire, votre experience, vos points forts...",
        height=120
    )

    photos_uploadees = st.file_uploader(
        "Photos de vos realisations (jusqu'a 5) - en ajouter de nouvelles remplace les anciennes",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    submit = st.form_submit_button("Enregistrer ma fiche", type="primary")

    if submit:
        if not nom_entreprise.strip() or not telephone.strip() or not ville_base.strip():
            st.error("Merci de renseigner au minimum le nom, le telephone et la ville de base.")
        elif not corps_metier_selectionnes:
            st.error("Merci de selectionner au moins un corps de metier.")
        else:
            dossier_artisan = os.path.join(UPLOAD_DIR, re.sub(r"[^a-zA-Z0-9]", "_", email_connecte))
            os.makedirs(dossier_artisan, exist_ok=True)

            chemins_photos = []
            if artisan and artisan.get("photos"):
                chemins_photos = [p for p in artisan["photos"].split(",") if p]

            if photos_uploadees:
                chemins_photos = []
                for i, photo in enumerate(photos_uploadees[:5]):
                    nom_fichier_propre = re.sub(r"[^a-zA-Z0-9._-]", "_", photo.name)
                    chemin = os.path.join(dossier_artisan, f"photo_{i}_{nom_fichier_propre}")
                    with open(chemin, "wb") as f:
                        f.write(photo.getbuffer())
                    chemins_photos.append(chemin)

            upsert_artisan(
                email=email_connecte,
                nom_entreprise=nom_entreprise.strip(),
                telephone=telephone.strip(),
                ville_base=ville_base.strip(),
                zones_desservies=zones_desservies.strip(),
                corps_metier_list=corps_metier_selectionnes,
                description=description.strip(),
                photos_paths=chemins_photos
            )
            st.success("Fiche enregistree avec succes.")
            st.rerun()

# --- APERCU DE LA FICHE PUBLIQUE + PLANNING ---
artisan = get_artisan_by_email(email_connecte)  # rechargement apres enregistrement eventuel

if artisan and artisan.get("nom_entreprise"):
    st.markdown("---")
    st.subheader("Apercu de votre fiche publique")

    col_photos, col_infos = st.columns([1, 2])
    with col_photos:
        photos_liste = [p for p in (artisan.get("photos") or "").split(",") if p and os.path.exists(p)]
        if photos_liste:
            for chemin_photo in photos_liste[:3]:
                st.image(chemin_photo, use_column_width=True)
        else:
            st.caption("Aucune photo ajoutee pour le moment.")

    with col_infos:
        st.markdown(f"### {artisan['nom_entreprise']}")
        st.write(f"Tel : {artisan['telephone']}")
        st.write(f"Base a : {artisan['ville_base']}")
        st.write(f"Intervient a : {artisan['zones_desservies']}")
        corps_affichage = (artisan.get("corps_metier") or "").replace(",", ", ")
        st.write(f"Corps de metier : {corps_affichage}")
        st.write(artisan.get("description") or "")

    # --- PLANNING / DISPONIBILITES (visible uniquement par l'artisan connecte) ---
    st.markdown("---")
    st.subheader("Votre planning (visible uniquement par vous)")
    st.caption(
        "Cochez les jours ou vous n'etes PAS disponible. "
        "Par defaut, tous les jours sont consideres comme disponibles."
    )

    jours_indispo_actuels = set(get_indisponibilites(artisan["id"]))

    horizon_jours = 30
    aujourd_hui = date.today()
    dates_horizon = [aujourd_hui + timedelta(days=i) for i in range(horizon_jours)]

    nouvelles_indispo = set()
    nb_colonnes = 7
    for semaine_debut in range(0, horizon_jours, nb_colonnes):
        colonnes = st.columns(nb_colonnes)
        for offset, col in enumerate(colonnes):
            idx = semaine_debut + offset
            if idx >= len(dates_horizon):
                continue
            jour = dates_horizon[idx]
            jour_str = jour.isoformat()
            coche = col.checkbox(
                jour.strftime("%d/%m"),
                value=(jour_str in jours_indispo_actuels),
                key=f"indispo_{jour_str}"
            )
            if coche:
                nouvelles_indispo.add(jour_str)

    if st.button("Enregistrer mon planning", type="primary"):
        set_indisponibilites(artisan["id"], sorted(nouvelles_indispo))
        st.success("Planning mis a jour.")
        st.rerun()
else:
    st.info("Completez et enregistrez votre fiche ci-dessus pour acceder a votre planning.")
