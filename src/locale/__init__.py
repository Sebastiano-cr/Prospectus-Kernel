"""Portas de localização (LocalePort) para internacionalização do Kirin."""
from .port import LocalePort
from .adapters.pt_br import PTBRLocaleAdapter
from .adapters.es import ESLocaleAdapter
from .adapters.en import ENLocaleAdapter
from .errors import LocaleNotFoundError

_locales: dict = {}


def get_locale(code: str = "pt-BR") -> LocalePort:
    if code not in _locales:
        if code == "pt-BR":
            _locales[code] = PTBRLocaleAdapter()
        elif code == "es":
            _locales[code] = ESLocaleAdapter()
        elif code == "en":
            _locales[code] = ENLocaleAdapter()
        else:
            raise LocaleNotFoundError(code)
    return _locales[code]


def register_locale(code: str, adapter: LocalePort) -> None:
    _locales[code] = adapter


def reset_locale() -> None:
    _locales.clear()


__all__ = ["LocalePort", "get_locale", "register_locale", "reset_locale"]
