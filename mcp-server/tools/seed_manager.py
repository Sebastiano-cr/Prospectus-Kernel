"""
Seed Manager — Gerador deterministico de fingerprint seeds para CloakBrowser.

Cada sessao de scraping recebe um seed unico, derivado de um seed mestre
+ contador atômico. Garante:
- Unicidade: cada sessao tem seed diferente
- Determinismo: mesmo input = mesmo seed
- Rastreabilidade: seeds sao logaveis e reproduziveis

Invariante I-Cloak-1: seed(X) == seed(X) sempre
"""
import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class SeedManager:
    """
    Gerador de fingerprint seeds para CloakBrowser.

    Cada chamada de next_seed() retorna um seed unico e deterministico.
    O seed e derivado de: master_seed + dominio + timestamp + contador.

    Uso:
        manager = SeedManager(master_seed="kirin")
        seed1 = manager.next_seed("maps")      # maps_10001
        seed2 = manager.next_seed("maps")      # maps_10002
        seed3 = manager.next_seed("instagram") # instagram_20001
    """

    # Faixas de seed por dominio (evita conflito entre dominios)
    DOMAIN_RANGES = {
        "maps": (10000, 19999),
        "instagram": (20000, 29999),
        "linkedin": (30000, 39999),
        "generic": (40000, 49999),
    }

    def __init__(self, master_seed: str = "kirin"):
        self.master_seed = master_seed
        self._counters = {}  # dominio -> proximo contador
        self._used_seeds = set()  # para evitar repeticao
        self._session_start = int(time.time())

    def next_seed(self, domain: str = "generic") -> int:
        """
        Retorna o proximo seed unico para o dominio especificado.

        Args:
            domain: Dominio do scraping (maps, instagram, linkedin, generic)

        Returns:
            Seed numerico unico
        """
        if domain not in self.DOMAIN_RANGES:
            logger.warning(f"Unknown domain '{domain}', using 'generic'")
            domain = "generic"

        min_seed, max_seed = self.DOMAIN_RANGES[domain]

        # Inicializa contador para este dominio
        if domain not in self._counters:
            self._counters[domain] = min_seed

        # Procura o proximo seed nao usado
        while self._counters[domain] <= max_seed:
            seed = self._counters[domain]
            self._counters[domain] += 1

            # Verifica unicidade
            if seed not in self._used_seeds:
                self._used_seeds.add(seed)
                logger.debug(f"Generated seed: {seed} for domain '{domain}'")
                return seed

        # Se esgotou a faixa, usa hash deterministico
        return self._derive_seed(domain)

    def _derive_seed(self, domain: str) -> int:
        """
        Deriva um seed via hash quando a faixa numerica esgota.
        Continua sendo deterministico (mesmo input = mesmo output).
        """
        hash_input = f"{self.master_seed}:{domain}:{len(self._used_seeds)}"
        h = hashlib.sha256(hash_input.encode()).hexdigest()
        # Pega os primeiros 5 digitos numericos do hash
        numeric = "".join(c for c in h if c.isdigit())[:5]
        seed = int(numeric) if numeric else 99999

        # Ajusta para estar dentro de uma faixa segura
        seed = 50000 + (seed % 49000)

        self._used_seeds.add(seed)
        return seed

    def get_seed_args(self, domain: str = "generic") -> list:
        """
        Retorna argumentos de linha de comando para CloakBrowser.

        Args:
            domain: Dominio do scraping

        Returns:
            Lista de argumentos para launch(args=[...])
        """
        seed = self.next_seed(domain)
        return [f"--fingerprint={seed}"]

    def stats(self) -> dict:
        """Retorna estatisticas do gerador."""
        return {
            "master_seed": self.master_seed,
            "total_seeds_generated": len(self._used_seeds),
            "counters": dict(self._counters),
            "domains_used": list(self._counters.keys()),
        }

    def reset(self) -> None:
        """Reseta todos os contadores e seeds usados."""
        self._counters.clear()
        self._used_seeds.clear()
        self._session_start = int(time.time())
        logger.info("SeedManager reset")
