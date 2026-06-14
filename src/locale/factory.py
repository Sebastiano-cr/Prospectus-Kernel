"""
Factory de LocalePort.
Singleton por código de locale. Permite registro explícito para testes.
"""
from typing import Dict
from .port import LocalePort
from .errors import LocaleNotFoundError

_locales: Dict[str, LocalePort] = {}


def get_locale(code: str = "pt-BR") -> LocalePort:
    """Retorna adapter de locale (singleton por código).

    Args:
        code: Código do locale. Ex: 'pt-BR', 'es', 'pt-PT'.

    Returns:
        Instância de LocalePort para o código solicitado.

    Raises:
        LocaleNotFoundError: Se o código não estiver registrado.
    """
    if code not in _locales:
        if code == "pt-BR":
            from .adapters.pt_br import PTBRLocaleAdapter

            _locales[code] = PTBRLocaleAdapter()
        elif code == "es":
            from .adapters.es import ESLocaleAdapter

            _locales[code] = ESLocaleAdapter()
        elif code == "en":
            from .adapters.en import ENLocaleAdapter

            _locales[code] = ENLocaleAdapter()
        else:
            raise LocaleNotFoundError(code)
    return _locales[code]


def register_locale(code: str, adapter: LocalePort) -> None:
    """Registra um adapter de locale explicitamente (para testes ou locales custom)."""
    _locales[code] = adapter


def reset_locale() -> None:
    """Limpa todos os locales registrados. Útil para testes."""
    _locales.clear()
