"""
Estimation IA Immo - MVP Streamlit
Estime le coût des travaux d'une pièce à partir de photos + contexte.

Lancer avec : streamlit run app.py
Nécessite une variable d'environnement ANTHROPIC_API_KEY (ou st.secrets)
"""

import base64
import json
import os

import streamlit as st
from anthropic import Anthropic

from calcul_devis import charger_base_prix, calculer_devis
from prompts import SYSTEM_PROMPT_TEMPLATE

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Estimation IA Immo", page_icon="🏗️", layout="wide")

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", st.secrets.get("ANTHROPIC_API_KEY", "")))
BASE_PRIX = charger_base_prix("base_prix_travaux.json")

LABELS_LOCALISATION = {k: v["label"] for k, v in BASE_PRIX["coefficients"]["localisation"].items()}
LABELS_ETAT = {k: v["label"] for k, v in BASE_PRIX["coefficients"]["etat_bien"].items()}
LABELS_GAMME = {"eco": "Éco", "standard": "Standard", "premium": "Premium"}


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------
def encoder_image_base64(fichier) -> tuple[str, str]:
    """Retourne (media_type, base64_data) pour un fichier uploadé Streamlit."""
    media_type = fichier.type  # ex: 'image/jpeg'
    data = base64.standard_b64encode(fichier.getvalue()).decode("utf-8")
    return media_type, data


def analyser_photos(photos, niveau_travaux_label: str, gamme_label: str) -> dict:
    """Appelle l'API Claude vision et retourne le JSON des postes détectés."""
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        niveau_travaux=niveau_travaux_label,
        gamme=gamme_label,
    )

    content_blocks = []
    for photo in photos:
        media_type, data = encoder_image_base64(photo)
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })
    content_blocks.append({
        "type": "text",
        "text": "Voici les photos de la pièce à analyser. Réponds uniquement avec le JSON demandé.",
    })

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": content_blocks}],
    )

    texte_reponse = "".join(block.text for block in response.content if block.type == "text")
    texte_nettoye = texte_reponse.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(texte_nettoye)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
st.title("🏗️ Estimation IA des travaux")
st.caption("Téléversez des photos d'une pièce pour obtenir une estimation instantanée du coût des travaux.")

with st.form("formulaire_estimation"):
    col1, col2 = st.columns([1, 1])

    with col1:
        photos = st.file_uploader(
            "Photos de la pièce (1 à 5)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )

    with col2:
        localisation = st.selectbox(
            "Localisation du bien",
            options=list(LABELS_LOCALISATION.keys()),
            format_func=lambda k: LABELS_LOCALISATION[k],
        )
        etat_bien = st.selectbox(
            "Niveau de travaux envisagé",
            options=list(LABELS_ETAT.keys()),
            format_func=lambda k: LABELS_ETAT[k],
        )
        gamme = st.selectbox(
            "Gamme choisie",
            options=list(LABELS_GAMME.keys()),
            format_func=lambda k: LABELS_GAMME[k],
        )

    submit = st.form_submit_button("Estimer les travaux", use_container_width=True)

if submit:
    if not photos or len(photos) == 0:
        st.error("Merci de téléverser au moins une photo.")
    elif len(photos) > 5:
        st.error("5 photos maximum.")
    else:
        with st.spinner("Analyse des photos par l'IA en cours..."):
            try:
                resultat_ia = analyser_photos(photos, LABELS_ETAT[etat_bien], LABELS_GAMME[gamme])
            except Exception as e:
                st.error(f"Erreur lors de l'analyse IA : {e}")
                st.stop()

        st.session_state["resultat_ia"] = resultat_ia
        st.session_state["params"] = {"localisation": localisation, "etat_bien": etat_bien, "gamme": gamme}

# ---------------------------------------------------------------------------
# Restitution des résultats
# ---------------------------------------------------------------------------
if "resultat_ia" in st.session_state:
    resultat_ia = st.session_state["resultat_ia"]
    params = st.session_state["params"]

    st.subheader(f"Pièce détectée : {resultat_ia.get('piece_detectee', 'N/A')}")
    st.info(resultat_ia.get("observations_generales", ""))

    devis = calculer_devis(
        postes_detectes=resultat_ia["postes_detectes"],
        localisation=params["localisation"],
        etat_bien=params["etat_bien"],
        gamme=params["gamme"],
        base=BASE_PRIX,
    )

    st.subheader("📋 Devis estimatif")
    st.dataframe(
        [
            {
                "Poste": l["nom"],
                "Quantité": l["quantite"],
                "Unité": l["unite"],
                "Prix unitaire HT": f"{l['prix_unitaire_ht']} €",
                "Coût HT": f"{l['cout_ht']:.2f} €",
                "Confiance": l["confiance"],
            }
            for l in devis["lignes"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Sous-total HT", f"{devis['sous_total_ht']:.2f} €")
    col_b.metric(f"Marge sécurité ({devis['marge_securite_pct']}%)", f"{devis['marge_securite_montant']:.2f} €")
    col_c.metric("Total estimé HT", f"{devis['total_ht']:.2f} €")

    st.caption(
        "⚠️ Estimation indicative basée sur une analyse visuelle par IA, sans métré ni "
        "visite technique. À affiner avec un professionnel avant tout engagement."
    )

    # Export PDF -> voir export_pdf.py pour l'implémentation avec fpdf2
    if st.button("📄 Générer le PDF"):
        from export_pdf import generer_pdf_devis
        chemin_pdf = generer_pdf_devis(devis, resultat_ia)
        with open(chemin_pdf, "rb") as f:
            st.download_button("Télécharger le devis PDF", f, file_name="devis_estimatif.pdf")
