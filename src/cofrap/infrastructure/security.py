import hashlib
import secrets
import string
from datetime import datetime

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet


class CryptoSecurity:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
        self.hasher = PasswordHasher()
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(24))

    def generate_password(self) -> str:
        categories = (string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%&*+-=?_")
        characters = [secrets.choice(category) for category in categories]
        alphabet = "".join(categories)
        characters.extend(secrets.choice(alphabet) for _ in range(20))
        secrets.SystemRandom().shuffle(characters)
        return "".join(characters)

    def hash_password(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify_password(self, password_hash: str, password: str) -> bool:
        try:
            return self.hasher.verify(password_hash or self.dummy_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self.cipher.decrypt(value.encode()).decode()

    def token(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def totp_secret(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, username: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="COFRAP")

    def verify_totp(
        self, secret: str, code: str, now: datetime, last_step: int | None
    ) -> int | None:
        step = int(now.timestamp()) // 30
        totp = pyotp.TOTP(secret)
        for candidate in (step, step - 1, step + 1):
            if last_step is not None and candidate <= last_step:
                continue
            if secrets.compare_digest(totp.at(candidate * 30), code):
                return candidate
        return None
