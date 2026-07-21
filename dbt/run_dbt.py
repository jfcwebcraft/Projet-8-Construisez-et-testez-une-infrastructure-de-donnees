"""
Wrapper pour exécuter dbt depuis ce projet.
Usage : python dbt/run_dbt.py <commande dbt>
Ex :    python dbt/run_dbt.py run
        python dbt/run_dbt.py test
        python dbt/run_dbt.py docs generate
"""
import sys
from pathlib import Path
import os

# On se positionne dans le dossier du projet dbt
os.chdir(Path(__file__).parent)

from dbt.cli.main import cli

if __name__ == "__main__":
    sys.argv = ["dbt"] + sys.argv[1:]
    try:
        cli()
    except SystemExit:
        pass
