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
import plotly.express as px

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


@st.cache_data
def construire_mapping_categories(_base_prix):
    """Construit dynamiquement le mapping id_poste -> corps de métier
    à partir des catégories définies dans base_prix_travaux.json.
    Ainsi, ajouter un poste dans le JSON suffit : pas besoin de toucher au code."""
    mapping = {}
    ordre_categories = []
    for cat in _base_prix["categories_travaux"]:
        nom_cat = cat["nom_categorie"]
        ordre_categories.append(nom_cat)
        for poste in cat["postes"]:
            mapping[poste["id"]] = nom_cat
    return mapping, ordre_categories


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
            "text": "Analyse ces photos de la pièce et retourne un JSON structuré avec la liste "
                    "des travaux nécessaires, en utilisant uniquement les IDs valides."
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

        # Cas où le modèle renvoie une chaîne JSON au lieu d'un vrai tableau
        if isinstance(postes, str):
            try:
                postes = json.loads(postes)
            except json.JSONDecodeError:
                postes = None

        if not postes:
            st.warning("⚠️ Aucun poste de travaux détecté sur ces photos. Essayez avec d'autres images.")
            st.stop()

        # Validation stricte : on ne garde que les postes bien formés
        postes_valides = [p for p in postes if isinstance(p, dict) and "id_poste" in p]

        if not postes_valides:
            st.error("❌ La réponse de l'IA est mal structurée (postes invalides). Réessayez.")
            with st.expander("🔍 Détail technique (pour diagnostic)"):
                st.write("Type de `postes_detectes` :", type(postes))
                st.json(postes)
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

    # 1. Charger la base de données JSON (mise en cache) + mapping catégories
    base_prix = charger_base_prix()
    id_vers_categorie, ordre_categories = construire_mapping_categories(base_prix)

    def get_categorie(id_poste):
        return id_vers_categorie.get(id_poste, "Autres")

    # 2. Préparer les données pour le Tableau Modifiable
    raw_postes = st.session_state["data_ia"]

    # Garde-fou : purge les entrées mal formées (ex: ancien format resté en session)
    raw_postes = [p for p in raw_postes if isinstance(p, dict) and "id_poste" in p]
    if not raw_postes:
        st.error("❌ Données d'analyse invalides. Cliquez sur '🔄 Nouvelle analyse' pour relancer.")
        st.stop()

    # --- Filtre par type de travaux (corps de métier) ---
    st.markdown("### 🧰 Corps de métier à inclure dans le devis")
    categories_presentes = sorted(
        {get_categorie(p.get("id_poste", "")) for p in raw_postes},
        key=lambda c: ordre_categories.index(c) if c in ordre_categories else 99
    )

    categories_selectionnees = st.multiselect(
        "Décochez les corps de métier que vous ne souhaitez pas inclure :",
        options=categories_presentes,
        default=categories_presentes,
        help="Seuls les postes détectés par l'IA appartenant aux corps de métier cochés apparaîtront dans le devis."
    )

    raw_postes_filtres = [
        p for p in raw_postes
        if get_categorie(p.get("id_poste", "")) in categories_selectionnees
    ]

    nb_exclus = len(raw_postes) - len(raw_postes_filtres)
    if nb_exclus > 0:
        st.caption(f"ℹ️ {nb_exclus} poste(s) exclu(s) du devis suite au filtre par corps de métier.")

    if not raw_postes_filtres:
        st.warning("⚠️ Aucun poste à afficher : sélectionnez au moins un corps de métier ci-dessus.")
        st.stop()

    raw_postes = raw_postes_filtres

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

    # Dictionnaire plat pour retrouver l'unité de chaque poste (m², unité, forfait, ml)
    unite_dict = {}
    for cat in base_prix["categories_travaux"]:
        for p in cat["postes"]:
            unite_dict[p["id"]] = p.get("unite", "")

    for p in raw_postes:
        p_id = p.get("id_poste", "?")
        pu = prix_dict.get(p_id, 0)
        qte = p.get("quantite_estimee", 1.0)
        rows.append({
            "Inclure": True,
            "Catégorie": get_categorie(p_id),
            "ID Poste": p_id,
            "Conseil IA": p.get("explication", ""),
            "Unité": unite_dict.get(p_id, ""),
            "Quantité": float(qte),
            "Prix Unitaire HT (€)": float(pu),
        })

    df_initial = pd.DataFrame(rows)

    edited_df = st.data_editor(
        df_initial,
        num_rows="dynamic",  # Permet d'ajouter/supprimer des lignes
        column_order=["Inclure", "Catégorie", "ID Poste", "Conseil IA", "Unité", "Quantité", "Prix Unitaire HT (€)"],
        column_config={
            "Inclure": st.column_config.CheckboxColumn(
                "✅ Inclure", default=True,
                help="Décochez pour exclure ce poste du devis et de la répartition par corps de métier"
            ),
            "Catégorie": st.column_config.SelectboxColumn(
                "Corps de métier", options=ordre_categories, required=True,
                help="Vous pouvez reclasser un poste dans un autre corps de métier"
            ),
            "ID Poste": st.column_config.TextColumn("Identifiant", disabled=True),
            "Conseil IA": st.column_config.TextColumn("Conseil IA"),
            "Unité": st.column_config.TextColumn("Unité", disabled=True),
            "Quantité": st.column_config.NumberColumn("Quantité", min_value=0.0, step=0.5, format="%.1f"),
            "Prix Unitaire HT (€)": st.column_config.NumberColumn("Prix U. (€ HT)", min_value=0.0, format="%.2f €"),
        },
        use_container_width=True
    )

    # 3. Calculs dynamiques basés sur le tableau édité (seules les lignes "Inclure" cochées comptent)
    coeff_loc = base_prix["coefficients"]["localisation"][localisation]["coefficient"]
    coeff_etat = base_prix["coefficients"]["etat_bien"][etat_bien]["coefficient"]

    edited_df["Sous-Total HT (€)"] = edited_df["Quantité"] * edited_df["Prix Unitaire HT (€)"] * coeff_loc * coeff_etat

    df_devis = edited_df[edited_df["Inclure"] == True].copy()  # noqa: E712
    sous_total_ht = df_devis["Sous-Total HT (€)"].sum()

    nb_exclus_checkbox = len(edited_df) - len(df_devis)
    if nb_exclus_checkbox > 0:
        st.caption(f"ℹ️ {nb_exclus_checkbox} poste(s) décoché(s), exclu(s) du calcul du devis.")

    montant_imponderables = sous_total_ht * (marge_pct / 100.0)
    total_general_ht = sous_total_ht + montant_imponderables

    # 3bis. Ventilation par corps de métier (sous-totaux + camembert)
    if sous_total_ht > 0:
        st.markdown("### 🧱 Répartition par corps de métier")
        repartition = (
            df_devis.groupby("Catégorie")["Sous-Total HT (€)"]
            .sum()
            .reset_index()
            .sort_values("Sous-Total HT (€)", ascending=False)
        )
        repartition["Part du budget"] = (repartition["Sous-Total HT (€)"] / sous_total_ht * 100).round(1)

        col_tableau, col_camembert = st.columns([1, 1])

        with col_tableau:
            st.dataframe(
                repartition,
                column_config={
                    "Catégorie": st.column_config.TextColumn("Corps de métier"),
                    "Sous-Total HT (€)": st.column_config.NumberColumn("Sous-total HT (€)", format="%.2f €"),
                    "Part du budget": st.column_config.NumberColumn("Part du budget", format="%.1f %%")
                },
                hide_index=True,
                use_container_width=True
            )

        with col_camembert:
            fig = px.pie(
                repartition,
                names="Catégorie",
                values="Sous-Total HT (€)",
                hole=0.4
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=350)
            st.plotly_chart(fig, use_container_width=True)

    # 4. Affichage des Métriques Financières
    st.markdown("### 💰 Récapitulatif Financier")

    surface_piece = st.number_input(
        "Surface au sol de la pièce (m²) — pour le calcul du prix au m²",
        min_value=1.0,
        max_value=200.0,
        value=st.session_state.get("surface_piece", 15.0),
        step=1.0,
        key="surface_piece"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sous-total Travaux (HT)", f"{sous_total_ht:,.2f} €".replace(",", " "))
    c2.metric(f"Sécurité & Impondérables ({marge_pct}%)", f"{montant_imponderables:,.2f} €".replace(",", " "))
    c3.metric("TOTAL ESTIMÉ (HT)", f"{total_general_ht:,.2f} €".replace(",", " "), delta=f"{marge_pct}% marge incluse")
    c4.metric("Prix au m²", f"{(total_general_ht / surface_piece):,.2f} €/m²".replace(",", " "))

    # 5. Export PDF (uniquement les postes cochés "Inclure")
    if st.button("📥 Télécharger le Devis au format PDF"):
        pdf_bytes = generer_pdf(df_devis, sous_total_ht, montant_imponderables, total_general_ht, marge_pct)
        st.download_button(
            label="Clic ici pour enregistrer le PDF",
            data=pdf_bytes,
            file_name="devis_estimation_travaux.pdf",
            mime="application/pdf"
        )
