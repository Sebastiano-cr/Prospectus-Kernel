from typing import Any, Dict, List


class LocalePort:
    """Base class para adapters de locale — implementações padrão lançam NotImplementedError."""

    language_code: str = ""

    def get_prompt(self, prompt_type: str, /, **context: Any) -> str:
        raise NotImplementedError

    def get_field_name(self, canonical_key: str) -> str:
        raise NotImplementedError

    def get_field_names(self, canonical_keys: List[str]) -> Dict[str, str]:
        raise NotImplementedError

    def get_score_category(self, score: int) -> str:
        raise NotImplementedError

    def get_score_ranges(self) -> Dict[str, tuple]:
        raise NotImplementedError

    def get_status_label(self, status_key: str) -> str:
        raise NotImplementedError

    def get_statuses(self) -> Dict[str, str]:
        raise NotImplementedError

    def get_fallback(self, key: str) -> str:
        raise NotImplementedError

    def get_markers(self, marker_type: str) -> List[str]:
        raise NotImplementedError

    def get_language_markers(self) -> Dict[str, List[str]]:
        raise NotImplementedError

    def get_parser_keywords(self, section: str) -> List[str]:
        raise NotImplementedError

    def get_json_only_suffix(self) -> str:
        raise NotImplementedError
