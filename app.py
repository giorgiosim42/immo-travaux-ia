import streamlit as st
import pandas as pd
import json
import os
import base64
import io
from PIL import Image
from anthropic import Anthropic
from calcul_devis import calculer_devis  # Assure-toi que cette fonction existe dans ton calcul_devis.py
from export_pdf import generer_pdf       # Assure-toi que cette fonction existe dans ton export_pdf.py
from prompts import SYSTEM_PROMPT        # Assure-toi que SYSTEM_PROMPT est défini

st.set_page_config(page_title="IA Immo - Estimation Travaux", page_icon="🏗️", layout="wide")

st.title("🏗️ Estimation IA de Travaux Immo")
st.markdown("Téléversez les photos d'une pièce et obtenez une estimation financière détaillée et ajustable.")


# --- FONCTIONS UTILITAIRES ---

def compress_image(file, max_size=1568, quality=85):
    """Redimensionne et compresse une image avant envoi à l'API (réduit coûts et payload)."""
    img = Image.open(file)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((max_size, max_size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


@st.cache_data
def charger_base_prix():
    """Charge la base de prix une seule fois (mise en cache)."""
    with open("base_prix_travaux.json", "r", encoding="utf-8") as f:
        return json.load(f)


# --- BARRE LATÉRALE : PARAMÈTRES ET COEFFICIENTS ---
st.sidebar.header("⚙️ Paramètres du projet")

localisation = st.sidebar.selectbox(
    "Localisation du bien",
    ["villes_moyennes_rural", "grandes_metropoles", "ile_de_france"],
    format_func=lambda x: {
        "villes_moyennes_rural": "Villes moyennes / Zones rurales (x1.0)",
        "grandes_metropoles": "Grandes métropoles (x1.15)",
        "ile_de_france": "Île-de-France / Paris (x1.20)"
    }[x]
)

etat_bien = st.sidebar.selectbox(
    "État initial constaté",
    ["rafraichissement", "renovation_moyenne", "renovation_lourde"],
    format_func=lambda x: {
        "rafraichissement": "Rafraîchissement léger",
        "renovation_moyenne": "Rénovation moyenne",
        "renovation_lourde": "Rénovation lourde / Démolition"
    }[x]
)

gamme_prix = st.sidebar.select_slider(
    "Gamme de prestations",
    options=["eco", "standard", "premium"],
    value="standard",
    format_func=lambda x: x.capitalize()
)

marge_pct = st.sidebar.slider(
    "Marge d'impondérables / Sécurité (%)",
    min_value=5,
    max_value=25,
    value=10,
    step=1,
    help="Pourcentage réservé aux imprévus de chantier (vices cachés, isolation, etc.)"
)

surface_piece = st.sidebar.number_input(
    "Surface au sol estimée de la pièce (m²)",
    min_value=1.0,
    max_value=200.0,
    value=15.0,
    step=1.0
)

# --- ZONE UPLOAD PHOTOS ---
uploaded_files = st.file_uploader(
    "Choisissez 1 à 5 photos de la pièce",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 5:
        st.warning("⚠️ Merci de limiter à 5 photos maximum. Seules les 5 premières seront analysées.")
        uploaded_files = uploaded_files[:5]

    cols = st.columns(len(uploaded_files))
    for idx, file in enumerate(uploaded_files):
        cols[idx].image(file, caption=f"Photo {idx + 1}", use_column_width=True)

# --- BOUTON DE GÉNÉRATION ET ANALYSE ---
if st.button("🚀 Lancer l'analyse IA", type="primary", disabled=not uploaded_files):
    api_key = st.secrets.get("ANTHROPIC_API_KEY") if hasattr(st, "secrets") else None
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        st.error("❌ Clé API Anthropic manquante. Ajoutez-la dans les Secrets Streamlit (ANTHROPIC_API_KEY).")
        st.stop()

    # Réinitialise l'état avant une nouvelle tentative
    st.session_state["analyse_effectuee"] = False

    progress_bar = st.progress(0, text="Préparation des images...")

    try:
        client = Anthropic(api_key=api_key)

        # --- Compression + encodage des images ---
        images_payload = []
        for idx, file in enumerate(uploaded_files):
            file.seek(0)
            compressed_bytes = compress_image(file)
            base64_image = base64.b64encode(compressed_bytes).decode("utf-8")
            images_payload.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",  # toujours JPEG après compression
                    "data": base64_image
                }
            })
            progress_bar.progress(
                (idx + 1) / len(uploaded_files),
                text=f"Photo {idx + 1}/{len(uploaded_files)} préparée..."
            )

        prompt_content = images_payload + [{
            "type": "text",
            "text": f"Analyse ces photos pour une pièce de {surface_piece} m2. "
                    f"Retourne un JSON structuré avec la liste des travaux nécessaires "
                    f"en utilisant uniquement les IDs valides."
        }]

        progress_bar.progress(1.0, text="Analyse par Claude en cours...")

        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            tools=[{
                "name": "retour_analyse",
                "description": "Retourne la liste structurée des travaux détectés sur les photos.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "postes_detectes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id_poste": {"type": "string"},
                                    "explication": {"type": "string"},
                                    "quantite_estimee": {"type": "number"},
                                    "niveau_confiance": {
                                        "type": "string",
                                        "enum": ["Élevé", "Moyen", "Faible"]
                                    }
                                },
                                "required": ["id_poste", "explication", "quantite_estimee", "niveau_confiance"]
                            }
                        }
                    },
                    "required": ["postes_detectes"]
                }
            }],
            tool_choice={"type": "tool", "name": "retour_analyse"},
            messages=[{"role": "user", "content": prompt_content}]
        )

        # Récupération directe du JSON structuré (plus de parsing texte fragile)
        tool_use_block = next(b for b in response.content if b.type == "tool_use")
        data_ia = tool_use_block.input

        postes = data_ia.get("postes_detectes")

        if not postes:
            st.warning("⚠️ Aucun poste de travaux détecté sur ces photos. Essayez avec d'autres images.")
            st.stop()

        # Validation stricte : on ne garde que les postes bien formés
        postes_valides = [p for p in postes if isinstance(p, dict) and "id_poste" in p]

        if not postes_valides:
            st.error("❌ La réponse de l'IA est mal structurée (postes invalides). Réessayez.")
            st.stop()

        st.session_state["data_ia"] = postes_valides
        st.session_state["analyse_effectuee"] = True
        progress_bar.empty()

    except StopIteration:
        st.error("❌ L'IA n'a pas retourné de résultat structuré. Réessayez.")
    except json.JSONDecodeError:
        st.error("❌ La réponse de l'IA n'a pas pu être interprétée. Réessayez.")
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg and "model" in error_msg.lower():
            st.error("❌ Le modèle IA configuré n'existe plus ou est indisponible. "
                      "Vérifiez le nom du modèle dans le code (ex: claude-sonnet-5).")
        elif "401" in error_msg or "authentication" in error_msg.lower():
            st.error("❌ Clé API invalide ou expirée. Vérifiez ANTHROPIC_API_KEY dans les Secrets.")
        else:
            st.error(f"❌ Erreur lors de l'analyse IA : {error_msg}")

# --- AFFICHAGE ET ÉDITION DU DEVIS (SI ANALYSE DÉJÀ EFFECTUÉE) ---
if st.session_state.get("analyse_effectuee"):
    st.markdown("---")
    st.subheader("📋 Devis Estimatif & Ajustement")
    st.info("💡 **Astuce :** Vous pouvez modifier directement les quantités ou les descriptions dans le tableau ci-dessous !")

    if st.button("🔄 Nouvelle analyse"):
        st.session_state["analyse_effectuee"] = False
        st.session_state.pop("data_ia", None)
        st.rerun()

    # 1. Charger la base de données JSON (mise en cache)
    base_prix = charger_base_prix()

    # 2. Préparer les données pour le Tableau Modifiable
    raw_postes = st.session_state["data_ia"]

    # Garde-fou : purge les entrées mal formées (ex: ancien format resté en session)
    raw_postes = [p for p in raw_postes if isinstance(p, dict) and "id_poste" in p]
    if not raw_postes:
        st.error("❌ Données d'analyse invalides. Cliquez sur '🔄 Nouvelle analyse' pour relancer.")
        st.stop()

    rows = []

    # Dictionnaire plat pour retrouver les prix unitaires
    prix_dict = {}
    for cat in base_prix["categories_travaux"]:
        for p in cat["postes"]:
            prix_dict[p["id"]] = p.get(f"prix_{gamme_prix}_ht", 0)

    postes_inconnus = [
        p.get("id_poste", "?") for p in raw_postes
        if p.get("id_poste") not in prix_dict
    ]
    if postes_inconnus:
        st.warning(
            f"⚠️ {len(postes_inconnus)} poste(s) non reconnu(s) dans la base de prix "
            f"(prix à 0€, à corriger manuellement) : {', '.join(postes_inconnus)}"
        )

    for p in raw_postes:
        p_id = p.get("id_poste", "?")
        pu = prix_dict.get(p_id, 0)
        qte = p.get("quantite_estimee", 1.0)
        rows.append({
            "ID Poste": p_id,
            "Description": p.get("explication", ""),
            "Quantité": float(qte),
            "Prix Unitaire HT (€)": float(pu),
            "Confiance IA": p.get("niveau_confiance", "Moyen")
        })

    df_initial = pd.DataFrame(rows)

    edited_df = st.data_editor(
        df_initial,
        num_rows="dynamic",  # Permet d'ajouter/supprimer des lignes
        column_config={
            "ID Poste": st.column_config.TextColumn("Identifiant", disabled=True),
            "Quantité": st.column_config.NumberColumn("Quantité", min_value=0.0, step=0.5, format="%.1f"),
            "Prix Unitaire HT (€)": st.column_config.NumberColumn("Prix U. (€ HT)", min_value=0.0, format="%.2f €"),
            "Confiance IA": st.column_config.SelectboxColumn("Confiance", options=["Élevé", "Moyen", "Faible"], disabled=True)
        },
        use_container_width=True
    )

    # 3. Calculs dynamiques basés sur le tableau édité
    coeff_loc = base_prix["coefficients"]["localisation"][localisation]["coefficient"]
    coeff_etat = base_prix["coefficients"]["etat_bien"][etat_bien]["coefficient"]

    edited_df["Sous-Total HT (€)"] = edited_df["Quantité"] * edited_df["Prix Unitaire HT (€)"] * coeff_loc * coeff_etat
    sous_total_ht = edited_df["Sous-Total HT (€)"].sum()

    montant_imponderables = sous_total_ht * (marge_pct / 100.0)
    total_general_ht = sous_total_ht + montant_imponderables

    # 4. Affichage des Métriques Financières
    st.markdown("### 💰 Récapitulatif Financier")
    c1, c2, c3 = st.columns(3)
    c1.metric("Sous-total Travaux (HT)", f"{sous_total_ht:,.2f} €".replace(",", " "))
    c2.metric(f"Sécurité & Impondérables ({marge_pct}%)", f"{montant_imponderables:,.2f} €".replace(",", " "))
    c3.metric("TOTAL ESTIMÉ (HT)", f"{total_general_ht:,.2f} €".replace(",", " "), delta=f"{marge_pct}% marge incluse")

    # 5. Export PDF
    if st.button("📥 Télécharger le Devis au format PDF"):
        pdf_bytes = generer_pdf(edited_df, sous_total_ht, montant_imponderables, total_general_ht, marge_pct)
        st.download_button(
            label="Clic ici pour enregistrer le PDF",
            data=pdf_bytes,
            file_name="devis_estimation_travaux.pdf",
            mime="application/pdf"
        )

