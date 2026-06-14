"""
Portas de localização (LocalePort) para internacionalização do Kirin.
Segue o mesmo padrão hexagonal de ILLMClient e IWhatsAppGateway.
"""
from .port import LocalePort
from .factory import get_locale, register_locale, reset_locale

__all__ = ["LocalePort", "get_locale", "register_locale", "reset_locale"]
