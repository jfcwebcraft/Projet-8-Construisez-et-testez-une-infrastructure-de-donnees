"""
Script batch pour exécuter plusieurs commandes dbt en séquence depuis Python.
Exécute : deps → seed → run → test → docs generate
"""
import os
import subprocess
import sys
from pathlib import Path

# Aller dans le dossier dbt
os.chdir(Path(__file__).parent)

# Lire le .env pour injecter le mot de passe dans l'environnement
env_file = Path(__file__).parents[1] / ".env"
env_vars = os.environ.copy()
for line in env_file.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env_vars[k.strip()] = v.strip()

def run_cmd(args: list[str]) -> bool:
    """Exécute une commande dbt et retourne True si succès."""
    cmd = [sys.executable, "-c",
           f"import sys; sys.argv=['dbt']+{args!r}; from dbt.cli.main import cli; cli()"]
    print(f"\n{'='*60}")
    print(f">>> dbt {' '.join(args)}")
    print('='*60)
    result = subprocess.run(cmd, env=env_vars, cwd=str(Path(__file__).parent))
    return result.returncode == 0


if __name__ == "__main__":
    # Séquence de commandes à exécuter (chaque élément est une liste d'arguments dbt)
    sequences = [
        ["deps"],
        ["seed"],
        ["run"],
        ["test"],
        ["docs", "generate"],
    ]

    # Si des arguments sont passés en ligne de commande, ne lancer que ceux-là
    if len(sys.argv) > 1:
        sequences = [[a] for a in sys.argv[1:]]

    tous_ok = True
    for args in sequences:
        ok = run_cmd(args)
        if not ok:
            print(f"\n[ERREUR] La commande 'dbt {' '.join(args)}' a échoué.")
            tous_ok = False
            break

    sys.exit(0 if tous_ok else 1)
