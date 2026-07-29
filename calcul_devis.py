"""
Module de calcul du devis à partir des postes détectés par l'IA
et de la base de prix (base_prix_travaux.json).

Formule : Coût = (Quantité * Prix Unitaire) * Coeff_Geographique * Coeff_Etat
Marge de sécurité : 10% appliquée sur le sous-total HT.
"""

import json
from pathlib import Path


def charger_base_prix(chemin_json: str = "base_prix_travaux.json") -> dict:
    with open(chemin_json, "r", encoding="utf-8") as f:
        return json.load(f)


def _trouver_poste(base: dict, poste_id: str) -> dict | None:
    """Recherche un poste par son id dans toutes les catégories."""
    for categorie in base["categories_travaux"]:
        for poste in categorie.get("postes", []):
            if poste["id"] == poste_id:
                return poste
    return None


def calculer_devis(
    postes_detectes: list[dict],
    localisation: str,
    etat_bien: str,
    gamme: str,
    base: dict,
) -> dict:
    """
    postes_detectes : liste d'objets {id, quantite_estimee, unite, confiance, justification}
                       (sortie brute de l'API vision)
    localisation : clé parmi 'ile_de_france' / 'grandes_metropoles' / 'villes_moyennes_rural'
    etat_bien : clé parmi 'rafraichissement' / 'renovation_moyenne' / 'renovation_lourde'
    gamme : 'eco' / 'standard' / 'premium'
    """
    coeff_geo = base["coefficients"]["localisation"][localisation]["coefficient"]
    coeff_etat = base["coefficients"]["etat_bien"][etat_bien]["coefficient"]
    prix_key = f"prix_{gamme}_ht"

    lignes = []
    sous_total = 0.0

    for item in postes_detectes:
        poste = _trouver_poste(base, item["id"])
        if poste is None:
            continue  # id inconnu renvoyé par le modèle -> on ignore par sécurité

        prix_unitaire = poste[prix_key]
        quantite = item["quantite_estimee"]
        cout_ligne = quantite * prix_unitaire * coeff_geo * coeff_etat

        lignes.append({
            "id": poste["id"],
            "nom": poste["nom"],
            "quantite": quantite,
            "unite": item.get("unite", poste["unite"]),
            "prix_unitaire_ht": prix_unitaire,
            "coeff_geo": coeff_geo,
            "coeff_etat": coeff_etat,
            "cout_ht": round(cout_ligne, 2),
            "confiance": item.get("confiance", "moyen"),
        })
        sous_total += cout_ligne

    # Marge de sécurité / impondérables (10% par défaut, configurable dans le JSON)
    marge_pct = base["metadata"].get("marge_securite_defaut_pct", 10)
    montant_marge = round(sous_total * marge_pct / 100, 2)

    total_ht = round(sous_total + montant_marge, 2)

    return {
        "lignes": lignes,
        "sous_total_ht": round(sous_total, 2),
        "marge_securite_pct": marge_pct,
        "marge_securite_montant": montant_marge,
        "total_ht": total_ht,
        "devise": base["metadata"].get("devise", "EUR"),
    }


if __name__ == "__main__":
    # Exemple rapide de test avec des données factices
    base = charger_base_prix()
    exemple_postes = [
        {"id": "peinture", "quantite_estimee": 25, "unite": "m2_surface_mur", "confiance": "moyen"},
        {"id": "revetement_sol_vinyle_parquet", "quantite_estimee": 12, "unite": "m2_surface_sol", "confiance": "eleve"},
        {"id": "chauffe_eau", "quantite_estimee": 1, "unite": "unite", "confiance": "eleve"},
    ]
    devis = calculer_devis(
        postes_detectes=exemple_postes,
        localisation="ile_de_france",
        etat_bien="renovation_moyenne",
        gamme="standard",
        base=base,
    )
    print(json.dumps(devis, indent=2, ensure_ascii=False))
