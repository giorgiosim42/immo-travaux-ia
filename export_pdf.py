from fpdf import FPDF
import pandas as pd

def generer_pdf(df_items: pd.DataFrame, sous_total: float, imponderables: float, total: float, marge_pct: int) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    
    # En-tête
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Devis Estimatif de Travaux - IA Immo", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    # Présentation des colonnes
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 8, "Poste / Description", border=1)
    pdf.cell(25, 8, "Quantite", border=1, align="C")
    pdf.cell(35, 8, "Prix U. HT (€)", border=1, align="R")
    pdf.cell(45, 8, "Sous-Total HT (€)", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    
    # Lignes du tableau
    pdf.set_font("Helvetica", "", 9)
    for _, row in df_items.iterrows():
        desc = str(row.get("Description", row.get("ID Poste", "Poste")))[:40]
        qte = float(row.get("Quantité", 0))
        pu = float(row.get("Prix Unitaire HT (€)", 0))
        st_row = float(row.get("Sous-Total HT (€)", qte * pu))
        
        pdf.cell(80, 7, desc, border=1)
        pdf.cell(25, 7, f"{qte:.1f}", border=1, align="C")
        pdf.cell(35, 7, f"{pu:.2f} €", border=1, align="R")
        pdf.cell(45, 7, f"{st_row:.2f} €", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Totaux
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 7, "Sous-total Travaux HT :", align="R")
    pdf.cell(45, 7, f"{sous_total:.2f} €", align="R", new_x="LMARGIN", new_y="NEXT")
    
    pdf.cell(140, 7, f"Marge Imponderables / Securite ({marge_pct}%) :", align="R")
    pdf.cell(45, 7, f"{imponderables:.2f} €", align="R", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(140, 9, "TOTAL GENERAL ESTIMATION HT :", align="R")
    pdf.cell(45, 9, f"{total:.2f} €", align="R", new_x="LMARGIN", new_y="NEXT")
    
    return bytes(pdf.output())
