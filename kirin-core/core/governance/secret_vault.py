import os
from datetime import datetime, timezone
from cryptography.fernet import Fernet


class SecretVault:
    def __init__(self) -> None:
        key = os.environ.get("SECRET_VAULT_KEY", Fernet.generate_key())
        if isinstance(key, str):
            key = key.encode()
        self._fernet = Fernet(key)
        self._audit: list[dict] = []

    def get(self, agent_id: str, secret_name: str) -> str:
        self._audit.append({
            "agent_id": agent_id,
            "secret_name": secret_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        encrypted = os.environ.get(secret_name, "")
        if encrypted:
            return self._fernet.decrypt(encrypted.encode()).decode()
        return ""

    def set(self, secret_name: str, value: str) -> None:
        os.environ[secret_name] = self._fernet.encrypt(value.encode()).decode()
