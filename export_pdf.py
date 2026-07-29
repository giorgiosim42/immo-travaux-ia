"""Export du devis estimatif en PDF avec fpdf2."""

from datetime import datetime

from fpdf import FPDF


def generer_pdf_devis(devis: dict, resultat_ia: dict, chemin_sortie: str = "devis_estimatif.pdf") -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Devis estimatif - Estimation IA Immo", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}", ln=True)
    pdf.cell(0, 8, f"Piece analysee : {resultat_ia.get('piece_detectee', 'N/A')}", ln=True)
    pdf.ln(4)

    # En-tête tableau
    pdf.set_font("Helvetica", "B", 10)
    largeurs = [70, 25, 30, 30, 25]
    entetes = ["Poste", "Quantite", "Prix unit. HT", "Cout HT", "Confiance"]
    for l, e in zip(largeurs, entetes):
        pdf.cell(l, 8, e, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for ligne in devis["lignes"]:
        pdf.cell(largeurs[0], 8, ligne["nom"][:40], border=1)
        pdf.cell(largeurs[1], 8, f"{ligne['quantite']} {ligne['unite']}", border=1)
        pdf.cell(largeurs[2], 8, f"{ligne['prix_unitaire_ht']} EUR", border=1)
        pdf.cell(largeurs[3], 8, f"{ligne['cout_ht']:.2f} EUR", border=1)
        pdf.cell(largeurs[4], 8, ligne["confiance"], border=1)
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Sous-total HT : {devis['sous_total_ht']:.2f} EUR", ln=True)
    pdf.cell(0, 8, f"Marge de securite ({devis['marge_securite_pct']}%) : {devis['marge_securite_montant']:.2f} EUR", ln=True)
    pdf.cell(0, 10, f"TOTAL ESTIME HT : {devis['total_ht']:.2f} EUR", ln=True)

    pdf.set_font("Helvetica", "I", 8)
    pdf.ln(6)
    pdf.multi_cell(
        0, 5,
        "Estimation indicative basee sur une analyse visuelle par intelligence "
        "artificielle, sans metre ni visite technique. A affiner avec un "
        "professionnel du batiment avant tout engagement financier."
    )

    pdf.output(chemin_sortie)
    return chemin_sortie
