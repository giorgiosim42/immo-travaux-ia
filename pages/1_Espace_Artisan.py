# -*- coding: utf-8 -*-
import streamlit as st
import os
import json
import re
import holidays
from datetime import date, timedelta

from db import (
    init_db,
    get_artisan_by_email,
    upsert_artisan,
    get_indisponibilites,
    set_indisponibilites,
)
from style import appliquer_style, cartouche, ORANGE_CHANTIER

st.set_page_config(page_title="Espace Artisan - IA Immo", page_icon="\U0001F477", layout="wide")

appliquer_style()
init_db()

UPLOAD_DIR = "uploads_artisans"
os.makedirs(UPLOAD_DIR, exist_ok=True)

JOURS_SEMAINE = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MOIS_FR = [
    "Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"
]


def ajouter_mois(annee, mois, delta):
    """Retourne (annee, mois) apres avoir ajoute delta mois a (annee, mois)."""
    total = (annee * 12 + (mois - 1)) + delta
    return total // 12, total % 12 + 1


@st.cache_data
def charger_corps_metier():
    with open("base_prix_travaux.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [cat["nom_categorie"] for cat in data["categories_travaux"]]



CORPS_METIER = charger_corps_metier()

cartouche(
    "Espace Artisan",
    "Créez votre fiche publique, définissez votre secteur d'intervention et gérez votre planning."
)

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
        value=(artisan.get("telephone") or "") if artisan else "",
        help="Ce numero sera visible publiquement par tous les visiteurs du site."
    )
    st.caption("\u26A0\uFE0F Ce numero sera visible par tous les clients sur le site (fiche publique).")

    st.markdown("**Secteur geographique d'intervention**")
    col_ville, col_rayon = st.columns([1, 2])
    with col_ville:
        ville_centre = st.text_input(
            "Ville de reference (centre de votre secteur)",
            value=(artisan.get("ville_base") or "") if artisan else "",
            placeholder="ex : Lyon"
        )
    with col_rayon:
        rayon_defaut = 20
        if artisan and artisan.get("rayon_km"):
            rayon_defaut = int(artisan["rayon_km"])
        rayon_km = st.slider(
            "Rayon d'intervention autour de cette ville (km)",
            min_value=5,
            max_value=100,
            value=rayon_defaut,
            step=5,
            help="Vous serez propose aux clients situes dans ce rayon autour de votre ville de reference."
        )
    if ville_centre.strip():
        st.caption(f"Vous intervenez dans un rayon de {rayon_km} km autour de {ville_centre.strip()}.")

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
        if not nom_entreprise.strip() or not telephone.strip() or not ville_centre.strip():
            st.error("Merci de renseigner au minimum le nom, le telephone et la ville de reference.")
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
                ville_base=ville_centre.strip(),
                rayon_km=rayon_km,
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

    with st.container(border=True):
        col_photos, col_infos = st.columns([1, 2])
        with col_photos:
            photos_liste = [p for p in (artisan.get("photos") or "").split(",") if p and os.path.exists(p)]
            if photos_liste:
                for chemin_photo in photos_liste[:3]:
                    st.image(chemin_photo, width="stretch")
            else:
                st.caption("Aucune photo ajoutee pour le moment.")

        with col_infos:
            st.markdown(f"### {artisan['nom_entreprise']}")
            st.write(f"Tel : {artisan['telephone']}")
            rayon_affiche = artisan.get("rayon_km") or 20
            st.write(f"Secteur : rayon de {rayon_affiche} km autour de {artisan['ville_base']}")
            corps_affichage = (artisan.get("corps_metier") or "").replace(",", ", ")
            st.write(f"Corps de metier : {corps_affichage}")
            st.write(artisan.get("description") or "")

    # --- PLANNING / DISPONIBILITES (visible uniquement par l'artisan connecte) ---
    st.markdown("---")
    st.subheader("Votre planning (visible uniquement par vous)")
    st.caption(
        "Cochez les jours ou vous n'etes PAS disponible. "
        "Par defaut, tous les jours a venir sont consideres comme disponibles."
    )

    aujourd_hui = date.today()

    # Les 12 prochains mois a partir du mois courant (peu importe quand on consulte la page)
    options_mois = [ajouter_mois(aujourd_hui.year, aujourd_hui.month, k) for k in range(12)]
    mois_selectionne = st.selectbox(
        "Mois a afficher",
        options=options_mois,
        format_func=lambda am: f"{MOIS_FR[am[1] - 1]} {am[0]}"
    )
    annee_sel, mois_sel = mois_selectionne

    premier_jour_mois = date(annee_sel, mois_sel, 1)
    annee_mois_suiv, mois_suiv = ajouter_mois(annee_sel, mois_sel, 1)
    dernier_jour_mois = date(annee_mois_suiv, mois_suiv, 1) - timedelta(days=1)

    # Grille calendaire complete (semaines entieres, du lundi au dimanche)
    lundi_debut_grille = premier_jour_mois - timedelta(days=premier_jour_mois.weekday())
    dimanche_fin_grille = dernier_jour_mois + timedelta(days=(6 - dernier_jour_mois.weekday()))
    nb_semaines_affichees = ((dimanche_fin_grille - lundi_debut_grille).days + 1) // 7

    jours_indispo_actuels = set(get_indisponibilites(artisan["id"]))
    nouvelles_indispo = set(jours_indispo_actuels)  # on part de l'existant, on ne modifie que les jours affiches

    # Jours feries francais sur toute la periode affichee (gere le changement d'annee)
    annees_concernees = list(range(lundi_debut_grille.year, dimanche_fin_grille.year + 1))
    jours_feries = holidays.France(years=annees_concernees)

    # --- Style "carnet de chantier" : cellules bordees bleu plan, weekends/feries grises,
    # + fond alterne par semaine (bleu plan / bleu calque), aujourd'hui en orange chantier ---
    cles_a_griser = []
    regles_fond_semaine = []
    for semaine in range(nb_semaines_affichees):
        lundi = lundi_debut_grille + timedelta(weeks=semaine)
        for i in range(7):
            jour = lundi + timedelta(days=i)
            if jour.weekday() >= 5 or jour in jours_feries:
                cles_a_griser.append(f"cellule_{jour.isoformat()}")

        couleur_fond = "rgba(27, 58, 107, 0.05)" if semaine % 2 == 0 else "rgba(92, 137, 172, 0.07)"
        regles_fond_semaine.append(
            f".st-key-semaine_{semaine} {{ background-color: {couleur_fond}; "
            f"border-radius: 4px; padding: 8px; }}"
        )

    regles_grisage = "\n".join(
        f".st-key-{cle} {{ background-color: rgba(120, 120, 120, 0.12) !important; "
        f"border-radius: 2px; }}"
        for cle in cles_a_griser
    )
    st.html(
        "<style>\n"
        + "\n".join(regles_fond_semaine) + "\n"
        + regles_grisage + "\n"
        + f".st-key-cellule_{aujourd_hui.isoformat()} {{ border: 2px solid {ORANGE_CHANTIER} !important; }}\n"
        + "</style>"
    )

    for semaine in range(nb_semaines_affichees):
        lundi = lundi_debut_grille + timedelta(weeks=semaine)
        dimanche = lundi + timedelta(days=6)
        numero_semaine_iso = lundi.isocalendar()[1]

        with st.container(key=f"semaine_{semaine}"):
            suffixe = " (cette semaine)" if lundi <= aujourd_hui <= dimanche else ""
            st.markdown(
                f"#### Semaine {numero_semaine_iso}{suffixe} "
                f"<span style='color:#888; font-weight:normal; font-size:0.9em;'>"
                f"&nbsp;&mdash;&nbsp;du {lundi.strftime('%d/%m')} au {dimanche.strftime('%d/%m')}</span>",
                unsafe_allow_html=True
            )

            colonnes = st.columns(7)
            for i, col in enumerate(colonnes):
                jour = lundi + timedelta(days=i)
                jour_str = jour.isoformat()
                est_aujourd_hui = (jour == aujourd_hui)
                est_passe = jour < aujourd_hui
                est_weekend = jour.weekday() >= 5
                est_hors_mois = jour.month != mois_sel
                nom_ferie = jours_feries.get(jour)

                with col:
                    with st.container(border=True, key=f"cellule_{jour_str}"):
                        couleur_texte = "#999" if (est_weekend or nom_ferie or est_hors_mois) else "inherit"
                        st.markdown(
                            f"<div style='text-align:center; color:{couleur_texte};'>"
                            f"<b>{JOURS_SEMAINE[i]}</b><br>{jour.strftime('%d/%m')}</div>",
                            unsafe_allow_html=True
                        )

                        if est_aujourd_hui:
                            st.markdown(
                                f"<div style='text-align:center; color:{ORANGE_CHANTIER}; font-size:0.75em;'>"
                                "Aujourd'hui</div>",
                                unsafe_allow_html=True
                            )
                        if nom_ferie:
                            st.markdown(
                                f"<div style='text-align:center; color:#b45309; font-size:0.75em;'>"
                                f"Ferie : {nom_ferie}</div>",
                                unsafe_allow_html=True
                            )

                        if est_passe:
                            st.caption("(passe)")
                        else:
                            coche = st.checkbox(
                                "Indisponible",
                                value=(jour_str in jours_indispo_actuels),
                                key=f"indispo_{jour_str}"
                            )
                            if coche:
                                nouvelles_indispo.add(jour_str)
                            else:
                                nouvelles_indispo.discard(jour_str)

        st.markdown("")  # petit espacement entre les semaines

    st.caption(
        "Cases grisees = weekend, jour ferie, ou jour hors du mois affiche. "
        "Cadre orange = aujourd'hui. Les bandes de couleur alternent pour separer les semaines."
    )

    if st.button("Enregistrer mon planning", type="primary"):
        set_indisponibilites(artisan["id"], sorted(nouvelles_indispo))
        st.success("Planning mis a jour.")
        st.rerun()
else:
    st.info("Completez et enregistrez votre fiche ci-dessus pour acceder a votre planning.")
