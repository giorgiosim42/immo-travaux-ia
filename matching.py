# -*- coding: utf-8 -*-
"""
Module de mise en relation client <-> artisans.

- Geocodage des villes via Nominatim (OpenStreetMap), gratuit, sans cle API.
  Usage raisonnable uniquement (voir politique Nominatim) : suffisant pour
  un prototype, a remplacer par Google Maps Geocoding si le trafic grandit.
- Calcul de distance a vol d'oiseau (formule de Haversine).
- Filtrage des artisans par corps de metier, rayon d'intervention et
  prochaine disponibilite.
"""

import math
from datetime import date, timedelta

import holidays
import requests
import streamlit as st

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim exige un User-Agent identifiable (pas de valeur par defaut type "python-requests").
USER_AGENT = "ImmoTravauxIA-Prototype/1.0"


@st.cache_data(show_spinner=False)
def geocoder_ville(nom_ville):
    """Convertit un nom de ville en (latitude, longitude) via Nominatim.
    Mis en cache : une meme ville n'est geocodee qu'une seule fois par session.
    Retourne None si la ville est vide, introuvable, ou en cas d'erreur reseau."""
    if not nom_ville or not nom_ville.strip():
        return None

    requete = nom_ville.strip()
    if "france" not in requete.lower():
        requete += ", France"

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": requete, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=5,
        )
        response.raise_for_status()
        resultats = response.json()
        if not resultats:
            return None
        return float(resultats[0]["lat"]), float(resultats[0]["lon"])
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None


def distance_km(lat1, lon1, lat2, lon2):
    """Distance a vol d'oiseau entre deux points GPS (formule de Haversine), en km."""
    rayon_terre = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * rayon_terre * math.asin(math.sqrt(a))


def prochaine_disponibilite(indisponibilites, jours_max=90, a_partir_de=None):
    """Retourne la prochaine date (jour ouvre, non ferie, non indisponible)
    a partir de `a_partir_de` (aujourd'hui par defaut), ou None si aucune trouvee
    dans les `jours_max` prochains jours a partir de ce point de depart.
    `indisponibilites` : liste de chaines 'YYYY-MM-DD' (issue de get_indisponibilites)."""
    indispo_set = set(indisponibilites)
    depart = a_partir_de or date.today()
    jours_feries = holidays.France(years=[depart.year, depart.year + 1])

    for offset in range(jours_max):
        jour = depart + timedelta(days=offset)
        if jour.weekday() >= 5:
            continue
        if jour in jours_feries:
            continue
        if jour.isoformat() in indispo_set:
            continue
        return jour
    return None


def trouver_artisans_correspondants(
    ville_client,
    corps_metier_requis,
    tous_les_artisans,
    get_indisponibilites_fn,
    date_debut=None,
    date_fin=None,
):
    """
    Filtre et trie les artisans pertinents pour un client donne.

    Parametres :
    - ville_client : ville saisie par le client (str)
    - corps_metier_requis : iterable des corps de metier presents dans le devis
    - tous_les_artisans : liste de dicts, telle que retournee par db.get_all_artisans()
    - get_indisponibilites_fn : fonction(artisan_id) -> liste de dates indisponibles
      (typiquement db.get_indisponibilites)
    - date_debut, date_fin : periode souhaitee par le client pour les travaux (objets date).
      Si fournis, la recherche de disponibilite commence a date_debut, et chaque artisan
      est marque "disponible sur la periode demandee" si son premier creneau libre tombe
      entre date_debut et date_fin inclus. Les artisans disponibles sur la periode sont
      remontes en tete de liste (a distance egale).

    Retourne :
    - None si la ville du client n'a pas pu etre geocodee
    - sinon, une liste de dicts artisans enrichis avec "distance_km",
      "prochaine_disponibilite" (objet date ou None) et "disponible_periode_demandee"
      (bool, ou None si aucune periode n'a ete precisee), triee par pertinence
    """
    coords_client = geocoder_ville(ville_client)
    if coords_client is None:
        return None

    lat_client, lon_client = coords_client
    corps_metier_requis = set(corps_metier_requis or [])
    resultats = []

    for artisan in tous_les_artisans:
        corps_artisan = set(c for c in (artisan.get("corps_metier") or "").split(",") if c)
        if corps_metier_requis and not (corps_artisan & corps_metier_requis):
            continue

        coords_artisan = geocoder_ville(artisan.get("ville_base", ""))
        if coords_artisan is None:
            continue

        lat_artisan, lon_artisan = coords_artisan
        distance = distance_km(lat_client, lon_client, lat_artisan, lon_artisan)

        rayon = artisan.get("rayon_km") or 20
        if distance > rayon:
            continue

        indispo = get_indisponibilites_fn(artisan["id"])
        prochaine = prochaine_disponibilite(indispo, a_partir_de=date_debut)

        disponible_periode = None
        if date_debut and date_fin:
            disponible_periode = bool(prochaine and date_debut <= prochaine <= date_fin)

        artisan_enrichi = dict(artisan)
        artisan_enrichi["distance_km"] = round(distance, 1)
        artisan_enrichi["prochaine_disponibilite"] = prochaine
        artisan_enrichi["disponible_periode_demandee"] = disponible_periode
        resultats.append(artisan_enrichi)

    # Tri : d'abord ceux disponibles sur la periode demandee (si une periode a ete precisee),
    # puis par distance croissante
    resultats.sort(key=lambda a: (not a["disponible_periode_demandee"], a["distance_km"]))
    return resultats
