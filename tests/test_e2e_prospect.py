#!/usr/bin/env python3
"""
Teste E2E: Mock MCP Server + kirin_prospect.py + Pair Backend real.

Fluxo:
  1. Sobe um HTTP server mockado que retorna leads do Google Maps
  2. Roda o kirin_prospect.py apontando para o mock + Pair Backend real
  3. Valida que o CSV foi gerado com os campos corretos
"""
import asyncio
import csv
import json
import os
import sys
import threading
import tempfile
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

import jwt

# Adicionar paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'kirin-pair-backend'))

# ---------------------------------------------------------------------------
# Mock MCP Server
# ---------------------------------------------------------------------------
MOCK_LEADS = [
    {
        "name": "Padaria Central",
        "address": "Rua Augusta 123, São Paulo",
        "phone": "+551199999999",
        "rating": 4.5,
        "google_maps_url": "https://maps.google.com/place/central"
    },
    {
        "name": "Clinica Sorriso",
        "address": "Av. Paulista 1000, São Paulo",
        "phone": "+5511988887777",
        "rating": 4.8,
        "google_maps_url": "https://maps.google.com/place/sorriso"
    },
    {
        "name": "Restaurante Sabor",
        "address": "Rua Oscar Freire 500, São Paulo",
        "phone": "+5511977776666",
        "rating": 4.2,
        "google_maps_url": "https://maps.google.com/place/sabor"
    }
]


class MockMCPHandler(BaseHTTPRequestHandler):
    """Handler que simula o MCP Server."""

    def do_POST(self):
        if self.path == "/tools/search_google_maps":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            limit = body.get("arguments", {}).get("limit", 10)
            response = {"result": MOCK_LEADS[:limit]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silenciar logs do servidor HTTP


def start_mock_server(port=13100):
    """Inicia o mock MCP Server em background."""
    server = HTTPServer(("127.0.0.1", port), MockMCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------
def test_e2e_full_pipeline():
    """Teste E2E: mock MCP → kirin_prospect → Pair Backend → CSV."""
    # 1. Iniciar mock MCP Server
    mock_port = 13100
    server = start_mock_server(mock_port)
    time.sleep(0.5)  # Dar tempo para o servidor iniciar

    # Verificar que o mock está rodando
    import urllib.request
    resp = urllib.request.urlopen(f"http://127.0.0.1:{mock_port}/health")
    assert resp.status == 200, "Mock MCP Server não iniciou"
    print("✅ Mock MCP Server rodando")

    try:
        # 2. Configurar variáveis de ambiente para o kirin_prospect
        csv_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
        csv_path = csv_file.name
        csv_file.close()

        os.environ["MCP_URL"] = f"http://127.0.0.1:{mock_port}"
        os.environ["PAIR_URL"] = "http://localhost:8002"
        os.environ["JWT_SECRET"] = "your-super-secret-jwt-key-change-this-in-production"
        os.environ["WORKSPACE_ID"] = "e2e-test"
        os.environ["OUTPUT_CSV"] = csv_path

        # Atualizar a constante OUTPUT_FILE no módulo
        import kirin_prospect
        kirin_prospect.MCP_URL = f"http://127.0.0.1:{mock_port}"
        kirin_prospect.OUTPUT_FILE = csv_path
        kirin_prospect.WORKSPACE_ID = "e2e-test"

        # 3. Rodar o pipeline
        print("▶ Executando kirin_prospect.run()...")
        results = asyncio.run(
            kirin_prospect.run("padaria", "São Paulo", 3)
        )

        # 4. Validar resultados
        print(f"\n📊 Resultados: {len(results)} leads processados")
        assert len(results) == 3, f"Esperado 3 leads, obtido {len(results)}"

        # Verificar que todos foram processados (pode ter erro de auth se o
        # Pair Backend não aceitar o token, mas o script deve tratar)
        ok_count = sum(1 for r in results if r["status"] == "ok")
        err_count = len(results) - ok_count
        print(f"  OK: {ok_count}, Erros: {err_count}")

        # Se houve erros, verificar se é de autenticação (esperado se
        # o workspace não existe)
        for r in results:
            print(f"  - {r['nome']}: status={r['status']}")

        # 5. Validar CSV
        assert os.path.exists(csv_path), f"CSV não foi criado: {csv_path}"
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"\n📄 CSV: {len(rows)} linhas")
        assert len(rows) == 3, f"CSV deveria ter 3 linhas, tem {len(rows)}"

        # Validar colunas
        expected_cols = ["nome", "telefone", "endereco", "avaliacao",
                        "pontuacao", "faixa", "mensagem", "status"]
        actual_cols = list(rows[0].keys())
        assert actual_cols == expected_cols, \
            f"Colunas erradas: {actual_cols} vs {expected_cols}"

        # Validar conteúdo
        assert rows[0]["nome"] == "Padaria Central"
        assert rows[0]["telefone"] == "+551199999999"
        assert rows[0]["endereco"] == "Rua Augusta 123, São Paulo"
        assert rows[0]["avaliacao"] == "4.5"

        print("✅ CSV validado com sucesso")

        # 6. Se algum lead foi processado com sucesso, verificar campos
        for r in results:
            if r["status"] == "ok":
                assert r["pontuacao"] != "", "Lead OK deve ter pontuação"
                assert r["faixa"] in ["frio", "morno", "quente"], \
                    f"Faixa inválida: {r['faixa']}"
                assert r["mensagem"] != "", "Lead OK deve ter mensagem"
                print(f"  ✅ {r['nome']}: score={r['pontuacao']} faixa={r['faixa']}")

        print("\n🎉 Teste E2E concluído com sucesso!")

    finally:
        server.shutdown()
        try:
            os.unlink(csv_path)
        except Exception:
            pass


def test_jwt_auth():
    """Teste: JWT token é gerado corretamente e aceito pelo Pair Backend."""
    import urllib.request

    secret = "your-super-secret-jwt-key-change-this-in-production"
    token = jwt.encode(
        {"sub": "test", "workspace_id": "test", "exp": time.time() + 3600},
        secret, algorithm="HS256"
    )

    # Testar com token válido (endpoint /test é POST)
    req = urllib.request.Request(
        "http://localhost:8002/test",
        data=b'{}',
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert data["workspace_id"] == "test"
    print("✅ JWT auth funcionando")

    # Testar com token inválido
    try:
        req2 = urllib.request.Request(
            "http://localhost:8002/test",
            data=b'{}',
            headers={
                "Authorization": "Bearer invalid-token",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        urllib.request.urlopen(req2)
        assert False, "Deveria ter retornado 401"
    except urllib.error.HTTPError as e:
        assert e.code == 401
        print("✅ JWT inválido rejeitado corretamente")


if __name__ == "__main__":
    print("=" * 60)
    print("TESTE E2E: kirin_prospect (MCP mock → Pair Backend → CSV)")
    print("=" * 60)
    print()

    test_jwt_auth()
    print()
    test_e2e_full_pipeline()
