"""
Testes para o SeedManager.

Cobre:
- I-Cloak-1: Determinismo de seeds
- Unicidade entre dominios
- Geração de argumentos para CloakBrowser
"""
import sys
import os
import pytest

# Adiciona o path do mcp-server para importacao
mcp_path = os.path.join(os.path.dirname(__file__), "..", "mcp-server")
if mcp_path not in sys.path:
    sys.path.insert(0, mcp_path)

from tools.seed_manager import SeedManager


class TestSeedManager:
    """Testes do SeedManager."""

    def test_next_seed_returns_int(self):
        """next_seed() retorna um inteiro."""
        sm = SeedManager(master_seed="test")
        seed = sm.next_seed("maps")
        assert isinstance(seed, int)

    def test_next_seed_unique_per_call(self):
        """Chamadas consecutivas retornam seeds diferentes."""
        sm = SeedManager(master_seed="test")
        seeds = [sm.next_seed("maps") for _ in range(10)]
        assert len(set(seeds)) == 10

    def test_seeds_different_domains_different_ranges(self):
        """Seeds de dominios diferentes estao em faixas diferentes."""
        sm = SeedManager(master_seed="test")
        maps_seed = sm.next_seed("maps")
        insta_seed = sm.next_seed("instagram")
        assert maps_seed < insta_seed

    def test_deterministic_same_master_seed(self):
        """Mesmo master_seed gera mesma sequencia de seeds."""
        sm1 = SeedManager(master_seed="kirin")
        sm2 = SeedManager(master_seed="kirin")
        
        seeds1 = [sm1.next_seed("maps") for _ in range(5)]
        seeds2 = [sm2.next_seed("maps") for _ in range(5)]
        assert seeds1 == seeds2

    def test_different_master_different_fallback_seeds(self):
        """Master seeds diferentes geram fallbacks diferentes quando faixa esgota."""
        sm1 = SeedManager(master_seed="kirin")
        sm2 = SeedManager(master_seed="other")
        
        # Esgota a faixa maps para ambos
        sm1._counters["maps"] = 19999
        sm2._counters["maps"] = 19999
        sm1.next_seed("maps")  # 19999
        sm2.next_seed("maps")  # 19999
        
        # Fallback usa master_seed no hash
        fallback1 = sm1.next_seed("maps")
        fallback2 = sm2.next_seed("maps")
        
        assert fallback1 != fallback2

    def test_get_seed_args_format(self):
        """get_seed_args() retorna formato correto para CloakBrowser."""
        sm = SeedManager(master_seed="test")
        args = sm.get_seed_args("maps")
        
        assert isinstance(args, list)
        assert len(args) == 1
        assert args[0].startswith("--fingerprint=")
        
        seed_value = int(args[0].split("=")[1])
        assert isinstance(seed_value, int)
        assert seed_value >= 10000

    def test_stats_reports_correctly(self):
        """stats() relata corretamente o estado."""
        sm = SeedManager(master_seed="test")
        sm.next_seed("maps")
        sm.next_seed("maps")
        sm.next_seed("instagram")
        
        stats = sm.stats()
        assert stats["total_seeds_generated"] == 3
        assert "maps" in stats["domains_used"]
        assert "instagram" in stats["domains_used"]
        assert stats["counters"]["maps"] == 10002
        assert stats["counters"]["instagram"] == 20001

    def test_reset_clears_state(self):
        """reset() limpa todo o estado."""
        sm = SeedManager(master_seed="test")
        sm.next_seed("maps")
        sm.next_seed("instagram")
        
        sm.reset()
        stats = sm.stats()
        assert stats["total_seeds_generated"] == 0
        assert stats["counters"] == {}

    def test_unknown_domain_falls_back_to_generic(self):
        """Dominio desconhecido cai em generic."""
        sm = SeedManager(master_seed="test")
        seed = sm.next_seed("unknown_platform")
        
        assert seed >= 40000  # faixa do generic
        assert seed <= 49999

    def test_seed_args_deterministic(self):
        """get_seed_args() e deterministico."""
        sm1 = SeedManager(master_seed="kirin")
        sm2 = SeedManager(master_seed="kirin")
        
        args1 = sm1.get_seed_args("maps")
        args2 = sm2.get_seed_args("maps")
        assert args1 == args2

    def test_exhaustion_uses_hash_fallback(self):
        """Quando faixa esgota, usa hash como fallback."""
        sm = SeedManager(master_seed="test")
        # Gera todos os seeds da faixa maps (10000-19999)
        # Isso e 10000 seeds, entao vamos testar com menos
        # Apenas verificamos que o fallback existe
        sm._counters["maps"] = 19999  # Quase no fim
        sm.next_seed("maps")  # 19999
        seed_overflow = sm.next_seed("maps")  # Deve usar fallback
        
        assert isinstance(seed_overflow, int)
        assert seed_overflow >= 50000  # Faixa do fallback
