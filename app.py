import streamlit as st
import pandas as pd
import json
import os
from anthropic import Anthropic
from calcul_devis import calculer_devis  # Assure-toi que cette fonction existe dans ton calcul_devis.py
from export_pdf import generer_pdf       # Assure-toi que cette fonction existe dans ton export_pdf.py

st.set_page_config(page_title="IA Immo - Estimation Travaux", page_icon="🏗️", layout="wide")

st.title("🏗️ Estimation IA de Travaux Immo")
st.markdown("Téléversez les photos d'une pièce et obtenez une estimation financière détaillée et ajustable.")

# --- BARRE LIATÉRALE : PARAMÈTRES ET COEFFICIENTS ---
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

# 💡 NOUVEAU : Curseur pour la marge d'impondérables dynamique
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
    cols = st.columns(len(uploaded_files))
    for idx, file in enumerate(uploaded_files):
        cols[idx].image(file, caption=f"Photo {idx+1}", use_column_width=True)

# --- BOUTON DE GÉNÉRATION ET ANALYSE ---
if st.button("🚀 Lancer l'analyse IA", type="primary", disabled=not uploaded_files):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("❌ Clé API Anthropic manquante dans les Secrets Streamlit.")
        st.stop()

    with st.spinner("Analyse des images par Claude 3.5 Sonnet..."):
        try:
            # Appel API Anthropic
            client = Anthropic(api_key=api_key)
            
            # --- Préparation des images pour l'API ---
            import base64
            images_payload = []
            for file in uploaded_files:
                file.seek(0)
                base64_image = base64.b64encode(file.read()).decode('utf-8')
                images_payload.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file.type,
                        "data": base64_image
                    }
                })

            prompt_content = images_payload + [{
                "type": "text",
                "text": f"Analyse ces photos pour une pièce de {surface_piece} m2. Retourne un JSON structuré avec la liste des travaux nécessaires en utilisant uniquement les IDs valides."
            }]

            from prompts import SYSTEM_PROMPT  # Assure-toi que SYSTEM_PROMPT est défini
            response = client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt_content}]
            )

            # Extraire le JSON de la réponse
            response_text = response.content[0].text
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            data_ia = json.loads(clean_json)

            # Stocker les résultats bruts dans la session
            st.session_state["data_ia"] = data_ia["postes_detectes"]
            st.session_state["analyse_effectuee"] = True

        except Exception as e:
            st.error(f"Erreur lors de l'analyse IA : {e}")

# --- AFFICHAGE ET ÉDITION DU DEVIS (SI ANALYSE DÉJÀ EFFECTUÉE) ---
if st.session_state.get("analyse_effectuee"):
    st.markdown("---")
    st.subheader("📋 Devis Estimatif & Ajustement")
    st.info("💡 **Astuce :** Vous pouvez modifier directement les quantites ou les descriptions dans le tableau ci-dessous !")

    # 1. Charger la base de données JSON
    with open("base_prix_travaux.json", "r", encoding="utf-8") as f:
        base_prix = json.load(f)

    # 2. Préparer les données pour le Tableau Modifiable
    raw_postes = st.session_state["data_ia"]
    rows = []
    
    # Dictionnaire plat pour retrouver les prix unitaires
    prix_dict = {}
    for cat in base_prix["categories_travaux"]:
        for p in cat["postes"]:
            prix_dict[p["id"]] = p.get(f"prix_{gamme_prix}_ht", 0)

    for p in raw_postes:
        p_id = p["id_poste"]
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

    # 💡 NOUVEAU : st.data_editor rend le tableau entièrement modifiable par l'utilisateur !
    edited_df = st.data_editor(
        df_initial,
        num_rows="dynamic", # Permet d'ajouter/supprimer des lignes
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

    # Calcul du sous-total
    edited_df["Sous-Total HT (€)"] = edited_df["Quantité"] * edited_df["Prix Unitaire HT (€)"] * coeff_loc * coeff_etat
    sous_total_ht = edited_df["Sous-Total HT (€)"].sum()
    
    # Application du pourcentage d'impondérables configuré dans le slider
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
