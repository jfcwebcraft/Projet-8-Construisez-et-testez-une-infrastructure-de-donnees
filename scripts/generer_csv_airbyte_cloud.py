"""
Génération des fichiers CSV sources pour Airbyte Cloud.

Ce script produit les 4 fichiers CSV qui seront hébergés sur GitHub
et lus par Airbyte Cloud via les URLs raw.githubusercontent.com.
Il reproduit exactement la logique des scripts d'extraction originaux
mais écrit dans data/airbyte_sources/ (inclus dans le versioning).

Usage :
    python scripts/generer_csv_airbyte_cloud.py
"""

import json
from pathlib import Path

import pandas as pd

# --- Chemins ---
RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "data" / "airbyte_sources"

# Sources (dans archives/reference/data/brut/)
FICHIER_INFOCLIMAT = RACINE / "archives" / "reference" / "data" / "brut" / "Data_Source1_011024-071024.json"
FICHIER_WU_ICHTEGEM = RACINE / "archives" / "reference" / "data" / "brut" / (
    "Weather Underground - Ichtegem, BE.xlsx"
)
FICHIER_WU_MADELEINE = RACINE / "archives" / "reference" / "data" / "brut" / (
    "Weather Underground - La Madeleine, FR.xlsx"
)


def generer_infoclimat_stations() -> int:
    """Extrait les métadonnées des 4 stations InfoClimat."""
    with open(FICHIER_INFOCLIMAT, "r", encoding="utf-8") as f:
        donnees = json.load(f)

    lignes = []
    for station in donnees["stations"]:
        licence = station.get("license", {})
        lignes.append({
            "id_station":            station["id"],
            "nom_station":           station["name"],
            "latitude":              station["latitude"],
            "longitude":             station["longitude"],
            "altitude_m":            station["elevation"],
            "type_station":          station["type"],
            "licence":               licence.get("license"),
            "licence_url":           licence.get("url"),
            "licence_source":        licence.get("source"),
            "licence_metadonnees_url": licence.get("metadonnees"),
        })

    df = pd.DataFrame(lignes)
    chemin = SORTIE / "infoclimat_stations.csv"
    df.to_csv(chemin, index=False, encoding="utf-8")
    print(f"✅ infoclimat_stations.csv   : {len(df):>6} lignes → {chemin}")
    return len(df)


def generer_infoclimat_releves() -> int:
    """Extrait les relevés horaires des 4 stations InfoClimat."""
    with open(FICHIER_INFOCLIMAT, "r", encoding="utf-8") as f:
        donnees = json.load(f)

    lignes = []
    for id_station, releves in donnees["hourly"].items():
        if id_station == "_params":
            continue
        for releve in releves:
            lignes.append(releve)

    df = pd.DataFrame(lignes)
    chemin = SORTIE / "infoclimat_releves.csv"
    df.to_csv(chemin, index=False, encoding="utf-8")
    print(f"✅ infoclimat_releves.csv    : {len(df):>6} lignes → {chemin}")
    return len(df)


def generer_wunderground(fichier_excel: Path, nom_sortie: str) -> int:
    """
    Concatène les feuilles journalières d'un classeur Weather Underground
    en un CSV unique. Les unités impériales (°F, mph, inHg) sont conservées
    telles quelles — la conversion vers le SI est faite dans le staging DBT.
    """
    xl = pd.ExcelFile(fichier_excel)
    frames = []
    for sheet in xl.sheet_names:
        try:
            df_feuille = pd.read_excel(xl, sheet_name=sheet, header=0)
            # Suppression des lignes entièrement vides
            df_feuille = df_feuille.dropna(how="all")
            if not df_feuille.empty:
                frames.append(df_feuille)
        except Exception as e:
            print(f"   ⚠️  Feuille ignorée '{sheet}' : {e}")

    if not frames:
        print(f"   ❌ Aucune feuille valide dans {fichier_excel.name}")
        return 0

    df = pd.concat(frames, ignore_index=True)
    chemin = SORTIE / f"{nom_sortie}.csv"
    df.to_csv(chemin, index=False, encoding="utf-8")
    print(f"✅ {nom_sortie}.csv : {len(df):>6} lignes → {chemin}")
    return len(df)


def main() -> None:
    print("=" * 60)
    print("  Génération des CSV pour Airbyte Cloud (GitHub hosting)")
    print("=" * 60)
    print(f"  Sortie : {SORTIE}")
    print()

    SORTIE.mkdir(parents=True, exist_ok=True)

    total = 0
    total += generer_infoclimat_stations()
    total += generer_infoclimat_releves()
    total += generer_wunderground(FICHIER_WU_ICHTEGEM, "wunderground_ichtegem")
    total += generer_wunderground(FICHIER_WU_MADELEINE, "wunderground_la_madeleine")

    print()
    print(f"  Total : {total} lignes dans 4 fichiers CSV")
    print()
    print("Prochaine étape : git add + push pour rendre les fichiers accessibles")
    print("sur raw.githubusercontent.com, puis configurer Airbyte Cloud.")


if __name__ == "__main__":
    main()
