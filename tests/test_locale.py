"""
Testes para src/locale/ — LocalePort + PTBRLocaleAdapter.
"""
import pytest
from src.locale import get_locale, register_locale, reset_locale, LocalePort
from src.locale.errors import LocaleNotFoundError, PromptNotFoundError


@pytest.fixture(autouse=True)
def clean_locales():
    reset_locale()
    yield
    reset_locale()


def test_get_locale_ptbr():
    loc = get_locale("pt-BR")
    assert loc.language_code == "pt-BR"


def test_get_locale_unknown():
    with pytest.raises(LocaleNotFoundError):
        get_locale("xx")


def test_register_locale():
    class MockLocale(LocalePort):
        language_code = "mock"
        def get_prompt(self, prompt_type, **ctx): return "mock"
        def get_field_name(self, key): return key
        def get_field_names(self, keys): return {k: k for k in keys}
        def get_score_category(self, score): return "mock"
        def get_score_ranges(self): return {}
        def get_status_label(self, key): return key
        def get_statuses(self): return {}
        def get_fallback(self, key): return key
        def get_markers(self, mtype): return []
        def get_language_markers(self): return {}
        def get_parser_keywords(self, section): return [section]
        def get_json_only_suffix(self): return "mock"

    register_locale("mock", MockLocale())
    loc = get_locale("mock")
    assert loc.language_code == "mock"


def test_field_name():
    loc = get_locale("pt-BR")
    assert loc.get_field_name("profile_summary") == "resumo_perfil"
    assert loc.get_field_name("weaknesses") == "pontos_fracos"
    assert loc.get_field_name("nonexistent") == "nonexistent"


def test_field_names_batch():
    loc = get_locale("pt-BR")
    result = loc.get_field_names(["profile_summary", "weaknesses"])
    assert result["profile_summary"] == "resumo_perfil"
    assert result["weaknesses"] == "pontos_fracos"


def test_score_categories():
    loc = get_locale("pt-BR")
    assert loc.get_score_category(72) == "quente"
    assert loc.get_score_category(45) == "morno"
    assert loc.get_score_category(15) == "frio"
    assert loc.get_score_category(100) == "quente"
    assert loc.get_score_category(0) == "frio"


def test_score_ranges():
    loc = get_locale("pt-BR")
    ranges = loc.get_score_ranges()
    assert ranges["hot"] == (70, 100)
    assert ranges["warm"] == (40, 69)
    assert ranges["cold"] == (0, 39)


def test_status_labels():
    loc = get_locale("pt-BR")
    assert loc.get_status_label("new") == "novo"
    assert loc.get_status_label("enriched") == "enriquecido"
    assert loc.get_status_label("message_sent") == "mensagem_enviada"


def test_fallbacks():
    loc = get_locale("pt-BR")
    assert loc.get_fallback("unknown_establishment") == "Estabelecimento desconhecido"
    assert loc.get_fallback("opt_out_message") == "\n\nResponda SAIR para não receber mais contatos."
    assert loc.get_fallback("nonexistent") == "nonexistent"


def test_json_only_suffix():
    loc = get_locale("pt-BR")
    suffix = loc.get_json_only_suffix()
    assert "JSON" in suffix
    assert "APENAS" in suffix


def test_markers():
    loc = get_locale("pt-BR")
    assert len(loc.get_markers("generic_phrases")) >= 3
    assert len(loc.get_markers("social_absence")) >= 3
    assert "raiva" in loc.get_markers("emotion_anger")
    unknown = loc.get_markers("unknown_type")
    assert unknown == []


def test_language_markers():
    loc = get_locale("pt-BR")
    markers = loc.get_language_markers()
    assert "pt" in markers
    assert "en" in markers
    assert "o " in markers["pt"]


def test_get_prompt_enricher():
    loc = get_locale("pt-BR")
    prompt = loc.get_prompt("enricher",
        name="Teste", address="Rua X", phone="11999999999",
        website="", instagram_username="",
        google_maps_data="{}", instagram_data="{}",
        field_profile_summary="resumo_perfil",
        field_weaknesses="pontos_fracos",
        field_opportunities="oportunidades",
        field_digital_maturity="maturidade_digital",
        maturity_high="alto", maturity_medium="médio", maturity_low="baixo",
        json_only_suffix=loc.get_json_only_suffix(),
    )
    assert "JSON" in prompt
    assert "resumo_perfil" in prompt


def test_get_prompt_unknown():
    loc = get_locale("pt-BR")
    with pytest.raises(PromptNotFoundError):
        loc.get_prompt("nonexistent_prompt_type")
