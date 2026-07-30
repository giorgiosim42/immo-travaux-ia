ffrom fpdf import FPDF
import pandas as pd
from datetime import datetime


def generer_pdf(df_items: pd.DataFrame, sous_total: float, imponderables: float, total: float, marge_pct: int) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    # --- En-tête ---
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Devis Estimatif de Travaux - IA Immo", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Genere le {datetime.now().strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # Largeurs de colonnes (mm) - total ~165mm
    W_POSTE, W_UNITE, W_QTE, W_PU, W_ST = 70, 20, 20, 27, 28

    def entete_tableau():
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(W_POSTE, 8, "Poste / Conseil IA", border=1, align="L", fill=True)
        pdf.cell(W_UNITE, 8, "Unite", border=1, align="C", fill=True)
        pdf.cell(W_QTE, 8, "Quantite", border=1, align="C", fill=True)
        pdf.cell(W_PU, 8, "Prix U. HT", border=1, align="R", fill=True)
        pdf.cell(W_ST, 8, "Sous-Total HT", border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")

    # Si aucune colonne "Categorie" (ancien format), on traite tout comme une seule categorie
    if "Catégorie" not in df_items.columns:
        df_items = df_items.copy()
        df_items["Catégorie"] = "Travaux"

    categories = df_items["Catégorie"].unique()

    for categorie in categories:
        df_cat = df_items[df_items["Catégorie"] == categorie]
        if df_cat.empty:
            continue

        # --- Bandeau de categorie ---
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(210, 225, 245)
        pdf.cell(0, 8, str(categorie), border=0, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        entete_tableau()

        pdf.set_font("Helvetica", "", 9)
        sous_total_cat = 0.0

        for _, row in df_cat.iterrows():
            desc = str(row.get("Conseil IA", row.get("Description", row.get("ID Poste", "Poste"))))
            desc = (desc[:55] + "...") if len(desc) > 55 else desc
            unite = str(row.get("Unité", "") or "-")
            qte = float(row.get("Quantité", 0) or 0)
            pu = float(row.get("Prix Unitaire HT (€)", 0) or 0)
            st_row = float(row.get("Sous-Total HT (€)", qte * pu) or 0)
            sous_total_cat += st_row

            pdf.cell(W_POSTE, 7, desc, border=1)
            pdf.cell(W_UNITE, 7, unite, border=1, align="C")
            pdf.cell(W_QTE, 7, f"{qte:.1f}", border=1, align="C")
            pdf.cell(W_PU, 7, f"{pu:.2f} EUR", border=1, align="R")
            pdf.cell(W_ST, 7, f"{st_row:.2f} EUR", border=1, align="R", new_x="LMARGIN", new_y="NEXT")

        # --- Sous-total de la categorie ---
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(W_POSTE + W_UNITE + W_QTE + W_PU, 7, f"Sous-total {categorie}", border=1, align="R")
        pdf.cell(W_ST, 7, f"{sous_total_cat:.2f} EUR", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # --- Totaux generaux ---
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 7, "Sous-total Travaux HT :", align="R")
    pdf.cell(45, 7, f"{sous_total:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.cell(140, 7, f"Marge Imponderables / Securite ({marge_pct}%) :", align="R")
    pdf.cell(45, 7, f"{imponderables:.2f} EUR", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(210, 225, 245)
    pdf.cell(140, 9, "TOTAL GENERAL ESTIMATION HT :", align="R", fill=True)
    pdf.cell(45, 9, f"{total:.2f} EUR", align="R", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(
        0, 5,
        "Devis estimatif genere par intelligence artificielle a partir de photos. "
        "Les montants sont indicatifs et ne remplacent pas un devis contractuel etabli par un professionnel du batiment."
    )

    return bytes(pdf.output())
