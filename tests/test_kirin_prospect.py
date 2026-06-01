"""Testes para kirin_prospect.py — script de cola MCP Server → Pair Backend."""
import sys
import os
import pytest

# Adicionar o diretório do script ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'kirin-pair-backend'))

import kirin_prospect
from kirin_prospect import map_lead_for_pair, _error_row, _save_csv
import tempfile
import csv


class TestMapLeadForPair:
    """Testes para o mapeamento de campos MCP → Pair Backend."""

    def test_map_full_place(self):
        """Mapeamento completo com todos os campos."""
        place = {
            "name": "Padaria Central",
            "address": "Rua Augusta, 123",
            "phone": "+551199999999",
            "rating": 4.5,
            "google_maps_url": "https://maps.google.com/place/123",
        }
        result = map_lead_for_pair(place)

        assert result["lead"]["name"] == "Padaria Central"
        assert result["lead"]["company"] == "Padaria Central"
        assert result["lead"]["title"] == "Proprietário"
        assert result["lead"]["phone"] == "+551199999999"
        assert result["lead"]["email"] == ""
        assert result["google_maps_data"]["address"] == "Rua Augusta, 123"
        assert result["google_maps_data"]["rating"] == 4.5
        assert "maps.google.com" in result["google_maps_data"]["google_maps_url"]

    def test_map_place_minimal(self):
        """Mapeamento com campos mínimos (sem telefone)."""
        place = {"name": "Loja Teste"}
        result = map_lead_for_pair(place)

        assert result["lead"]["name"] == "Loja Teste"
        assert result["lead"]["company"] == "Loja Teste"
        assert result["lead"]["phone"] == ""
        assert result["google_maps_data"]["address"] is None
        assert result["google_maps_data"]["rating"] is None

    def test_map_place_empty(self):
        """Mapeamento com dict vazio não deve quebrar."""
        result = map_lead_for_pair({})

        assert result["lead"]["name"] == ""
        assert result["lead"]["company"] == ""
        assert result["lead"]["phone"] == ""


class TestErrorRow:
    """Testes para geração de linhas de erro."""

    def test_error_row_basic(self):
        place = {"name": "Teste", "phone": "123", "address": "Rua X", "rating": 4.0}
        row = _error_row(place, "HTTP 500")

        assert row["nome"] == "Teste"
        assert row["telefone"] == "123"
        assert "HTTP 500" in row["status"]
        assert row["pontuacao"] == ""
        assert row["mensagem"] == ""


class TestSaveCSV:
    """Testes para persistência em CSV."""

    def test_save_and_read_csv(self):
        results = [
            {
                "nome": "Padaria Central",
                "telefone": "+551199999999",
                "endereco": "Rua Augusta, 123",
                "avaliacao": 4.5,
                "pontuacao": 85,
                "faixa": "quente",
                "mensagem": "Olá! Tudo bem?",
                "status": "ok",
            },
            {
                "nome": "Loja Teste",
                "telefone": "",
                "endereco": None,
                "avaliacao": None,
                "pontuacao": "",
                "faixa": "",
                "mensagem": "",
                "status": "erro: HTTP 401",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            tmpfile = f.name

        original_output = kirin_prospect.OUTPUT_FILE
        try:
            kirin_prospect.OUTPUT_FILE = tmpfile
            _save_csv(results)

            # Read back and validate
            with open(tmpfile, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["nome"] == "Padaria Central"
            assert rows[0]["pontuacao"] == "85"
            assert rows[0]["faixa"] == "quente"
            assert rows[1]["status"] == "erro: HTTP 401"
        finally:
            kirin_prospect.OUTPUT_FILE = original_output
            os.unlink(tmpfile)


class TestGenerateToken:
    """Testes para geração de token JWT."""

    def test_generate_token_structure(self):
        import jwt as pyjwt

        token = kirin_prospect.generate_token()
        payload = pyjwt.decode(
            token, kirin_prospect.JWT_SECRET, algorithms=["HS256"]
        )

        assert payload["workspace_id"] == kirin_prospect.WORKSPACE_ID
        assert "exp" in payload
        assert payload["sub"] == "prospect-script"
