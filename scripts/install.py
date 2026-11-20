"""Instala o projeto no ambiente virtual desta máquina. Execute com Python 3.12+."""
import argparse
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["dev", "prod"], default="dev", nargs="?")
    profile = parser.parse_args().profile
    if sys.version_info < (3, 12):
        parser.exit(1, "Use Python 3.12 ou superior.\n")

    root = Path(__file__).resolve().parents[1]
    venv = root / ".venv"
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    package = ".[test]" if profile == "dev" else "."
    subprocess.run([python, "-m", "pip", "install", "-e", package], cwd=root, check=True)

    template = root / (".env.example" if profile == "dev" else "deploy/production.env.example")
    dotenv = root / ".env"
    try:
        with dotenv.open("xb") as target:
            target.write(template.read_bytes())
    except FileExistsError:
        print("Usando o .env existente.", flush=True)

    result = subprocess.run([python, "-c", "from app.core.config import Settings; print(Settings().app_env)"],
                            cwd=root, stdout=subprocess.PIPE, text=True, check=True)
    expected = "development" if profile == "dev" else "production"
    if result.stdout.strip() != expected:
        parser.exit(1, f"Confira APP_ENV no ambiente e no .env. O perfil {profile} requer {expected}.\n")

    if profile == "dev":
        subprocess.run([python, "-m", "alembic", "upgrade", "head"], cwd=root, check=True)
        print("DEV pronto. Inicie os processos pelo script start da sua plataforma.")
    else:
        print("Dependências de produção instaladas. Revise o .env, escolha a base e aplique as migrações",
              "conforme docs/DEPLOY_SESC.md.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
