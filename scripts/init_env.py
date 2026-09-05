"""Génère une configuration locale sans écraser un fichier existant."""

import base64
import os
import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / ".env"
content = (
    "POSTGRES_USER=cofrap\n"
    f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
    "POSTGRES_DB=cofrap\nPOSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=55432\n"
    f"ENCRYPTION_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}\n"
    "PUBLIC_BASE_URL=http://localhost:8000\nCOOKIE_SECURE=false\n"
)
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print(".env existe déjà : aucune modification.")
else:
    with os.fdopen(fd, "w") as stream:
        stream.write(content)
    print(".env créé avec des secrets aléatoires (permissions 0600).")
