# -*- coding: utf-8 -*-
"""
Systeme de design partage : "Carnet de chantier"
--------------------------------------------------
Identite visuelle technique inspiree des plans d'architecte : bleu plan,
grille de calque en fond, typographie technique (IBM Plex), et un cartouche
d'en-tete (bandeau titre + reference) commun a toutes les pages.

Les couleurs de base (fond, texte, accent) sont deja gerees nativement par
`.streamlit/config.toml` (le plus robuste face aux changements de version
de Streamlit). Ce module ajoute uniquement ce que le theme natif ne couvre
pas : polices, texture de fond, cartouche, et bordures des cartes/metrics.

A appeler une seule fois, tout en haut de chaque page, juste apres
st.set_page_config() :

    from style import appliquer_style, cartouche
    appliquer_style()
    cartouche("Titre de la page", "Sous-titre / description courte")
"""
from datetime import date

import streamlit as st

# --- Palette (doit rester cohérente avec .streamlit/config.toml) ----------
BLEU_PLAN = "#1B3A6B"        # bleu plan technique : titres, bordures, structure
BLEU_CALQUE = "#5C89AC"      # bleu calque : accents secondaires
PAPIER = "#F3F5F2"           # fond principal
ENCRE = "#16202B"            # texte principal
ORANGE_CHANTIER = "#D9622B"  # accent action (boutons, "aujourd'hui", alertes)
VERT_TAMPON = "#3C7A5E"      # validation / disponibilite


def appliquer_style():
    """Injecte les polices, la texture de fond et les styles de composants."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        html, body, [data-testid="stAppViewContainer"] {{
            font-family: 'IBM Plex Sans', sans-serif;
            background-image:
                repeating-linear-gradient(0deg, rgba(27,58,107,0.05) 0px, rgba(27,58,107,0.05) 1px, transparent 1px, transparent 24px),
                repeating-linear-gradient(90deg, rgba(27,58,107,0.05) 0px, rgba(27,58,107,0.05) 1px, transparent 1px, transparent 24px);
        }}

        h1, h2, h3 {{
            font-family: 'IBM Plex Sans Condensed', sans-serif;
            font-weight: 700;
            color: {BLEU_PLAN};
            letter-spacing: 0.01em;
        }}

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            border-bottom: 1px solid {BLEU_PLAN};
            padding-bottom: 0.3rem;
        }}

        /* Cartes / metriques : fond blanc, bordure fine, accent gauche */
        [data-testid="stMetric"] {{
            background-color: #FFFFFF;
            border: 1px solid rgba(27,58,107,0.25);
            border-left: 4px solid {BLEU_PLAN};
            border-radius: 2px;
            padding: 0.75rem 1rem;
        }}
        [data-testid="stMetricValue"] {{
            font-family: 'IBM Plex Mono', monospace;
            color: {BLEU_PLAN};
        }}
        [data-testid="stMetricLabel"] {{
            font-family: 'IBM Plex Sans', sans-serif;
            opacity: 0.75;
        }}

        /* Conteneurs a bordure (st.container(border=True)) : cartes artisan, etc. */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 2px !important;
        }}

        /* Zones de depot / expanders : bordure en pointilles, esprit "zone de plan" */
        [data-testid="stExpander"],
        [data-testid="stFileUploaderDropzone"] {{
            border: 1px dashed {BLEU_CALQUE} !important;
            border-radius: 2px !important;
        }}

        hr {{
            border-top: 1px solid rgba(27,58,107,0.35) !important;
        }}

        code {{
            font-family: 'IBM Plex Mono', monospace;
            background-color: rgba(27,58,107,0.08);
            color: {BLEU_PLAN};
        }}

        button[kind="primary"] {{
            font-family: 'IBM Plex Sans Condensed', sans-serif;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            border-radius: 2px !important;
        }}
        button[kind="secondary"] {{
            border-radius: 2px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def cartouche(titre: str, sous_titre: str = "", reference: str | None = None):
    """Bandeau d'en-tete façon cartouche de plan technique : titre, sous-titre,
    et une bande de metadonnees reelles (date du jour, reference du document
    si fournie). Remplace st.title() en debut de page."""
    bande_meta = f'<span style="margin-right:1.5rem;">DATE&nbsp;&nbsp;{date.today().strftime("%d/%m/%Y")}</span>'
    if reference:
        bande_meta += f'<span>REF&nbsp;&nbsp;{reference}</span>'

    sous_titre_html = (
        f'<div style="font-family:\'IBM Plex Sans\',sans-serif; color:{ENCRE}; '
        f'opacity:0.75; margin-top:0.25rem; font-size:0.95rem;">{sous_titre}</div>'
        if sous_titre else ""
    )

    st.markdown(
        f"""
        <div style="border: 2px solid {BLEU_PLAN}; border-radius: 2px; margin-bottom: 1.3rem;">
            <div style="padding: 0.9rem 1.1rem 0.6rem 1.1rem;">
                <div style="font-family:'IBM Plex Sans Condensed',sans-serif; font-weight:700;
                            font-size:1.7rem; text-transform:uppercase; color:{BLEU_PLAN}; line-height:1.15;">
                    {titre}
                </div>
                {sous_titre_html}
            </div>
            <div style="border-top:1px solid {BLEU_PLAN}; padding:0.4rem 1.1rem;
                        font-family:'IBM Plex Mono',monospace; font-size:0.72rem;
                        color:{BLEU_PLAN}; background:rgba(27,58,107,0.05);">
                {bande_meta}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
