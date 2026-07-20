"""
Script de capture d'écran de l'interface Airbyte.
Utilise Playwright avec authentification HTTP basique (proxy Airbyte)
pour naviguer et capturer les connecteurs et l'historique de synchronisation.

Les identifiants sont lus depuis le fichier .env du projet
(AIRBYTE_BASIC_AUTH_USERNAME / AIRBYTE_BASIC_AUTH_PASSWORD).
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def charger_env() -> dict:
    """Lit le fichier .env à la racine du projet."""
    variables = {}
    chemin_env = Path(__file__).parents[1] / ".env"
    if chemin_env.exists():
        for ligne in chemin_env.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                cle, _, valeur = ligne.partition("=")
                variables[cle.strip()] = valeur.strip()
    return variables


_env = charger_env()
OUT_DIR = "screenshots/airbyte"
BASE_URL = f"http://localhost:{_env.get('AIRBYTE_WEBAPP_PORT', '8000')}"
USER = _env.get("AIRBYTE_BASIC_AUTH_USERNAME", os.environ.get("AIRBYTE_BASIC_AUTH_USERNAME", ""))
PASSWORD = _env.get("AIRBYTE_BASIC_AUTH_PASSWORD", os.environ.get("AIRBYTE_BASIC_AUTH_PASSWORD", ""))

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        http_credentials={"username": USER, "password": PASSWORD},
    )
    page = context.new_page()

    # 1. Page d'accueil / liste des connexions
    page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)

    # Si l'assistant de configuration initiale apparaît, le remplir puis le valider
    if "/setup" in page.url:
        try:
            page.locator("input[name='email']").fill("data-engineer@greencoop.fr")
            page.locator("input[name='organizationName']").fill("GreenCoop")
            page.wait_for_timeout(500)
            page.get_by_text("Get started", exact=False).first.click(timeout=5000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print("Impossible de passer l'écran de setup:", e)

    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT_DIR}/01_airbyte_accueil.png")

    # 2. Liste des sources configurées
    try:
        page.goto(f"{BASE_URL}/source", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT_DIR}/02_airbyte_sources.png")
    except Exception as e:
        print("Erreur page sources:", e)

    # 3. Liste des destinations configurées
    try:
        page.goto(f"{BASE_URL}/destination", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT_DIR}/03_airbyte_destinations.png")
    except Exception as e:
        print("Erreur page destinations:", e)

    # 4. Liste des connexions (sync)
    try:
        page.goto(f"{BASE_URL}/connections", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT_DIR}/04_airbyte_connections.png")
    except Exception as e:
        print("Erreur page connections:", e)

    # 5. Détail d'une connexion avec historique de synchronisation réussi
    try:
        import json as _json
        with open("scripts/_airbyte_connections.json", encoding="utf-8") as fp:
            conns = _json.load(fp)["connections"]
        first_conn_id = conns[0]["connection_id"]
        page.goto(
            f"{BASE_URL}/connections/{first_conn_id}/status",
            wait_until="networkidle", timeout=20000,
        )
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT_DIR}/05_airbyte_sync_status.png")

        page.goto(
            f"{BASE_URL}/connections/{first_conn_id}/job-history",
            wait_until="networkidle", timeout=20000,
        )
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT_DIR}/06_airbyte_sync_history.png")
    except Exception as e:
        print("Erreur page détail connexion:", e)

    browser.close()

print("Captures Airbyte terminées.")
