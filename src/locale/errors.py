class LocaleNotFoundError(LookupError):
    """Locale não encontrado no registro."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Locale '{code}' não encontrado. Locais registrados: pt-BR")


class PromptNotFoundError(FileNotFoundError):
    """Arquivo de prompt não encontrado para o locale."""

    def __init__(self, prompt_type: str, locale_code: str) -> None:
        self.prompt_type = prompt_type
        self.locale_code = locale_code
        super().__init__(f"Prompt '{prompt_type}' não encontrado para locale '{locale_code}'")
