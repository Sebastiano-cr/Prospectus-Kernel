"""
LocalePort — Porto de Localização (ABC).

Invariantes:
- Todo locale implementa todos os métodos.
- get_prompt() recebe o tipo do prompt como positional-only argument.
- get_field_name() mapeia de chave canônica (inglês) para o locale alvo.
- get_fallback() retorna string localizada para chave canônica.
- Métodos get_* nunca retornam None — sempre um valor default sensato.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LocalePort(ABC):
    """Porta de localização — invariante: todo locale implementa todos os métodos."""

    @property
    @abstractmethod
    def language_code(self) -> str:
        """Código do locale. Ex: 'pt-BR', 'es', 'pt-PT'."""
        ...

    # ── Prompts ──────────────────────────────────────────────────────────

    @abstractmethod
    def get_prompt(self, prompt_type: str, /, **context: Any) -> str:
        """Retorna prompt LLM preenchido com context.

        Args:
            prompt_type: Identificador do prompt.
                         Ex: 'enricher', 'scorer', 'messenger', 'researcher',
                             'discourse_ingestion', 'language_game',
                             'resonance', 'prospect', 'llm_judge_system'.
            **context: Variáveis de template para preencher o prompt.

        Returns:
            Prompt completo com variáveis substituídas.
        """
        ...

    # ── Schema fields ────────────────────────────────────────────────────

    @abstractmethod
    def get_field_name(self, canonical_key: str) -> str:
        """Mapeia chave canônica → nome do campo no schema do locale.

        Ex:
          'profile_summary'  → pt-BR='resumo_perfil',   es='resumen_del_perfil'
          'weaknesses'       → pt-BR='pontos_fracos',    es='puntos_débiles'
          'digital_maturity' → pt-BR='maturidade_digital'
        """
        ...

    @abstractmethod
    def get_field_names(self, canonical_keys: List[str]) -> Dict[str, str]:
        """Batch mapping — evita N chamadas individuais."""
        ...

    # ── Categorias de score ──────────────────────────────────────────────

    @abstractmethod
    def get_score_category(self, score: int) -> str:
        """Classifica score numérico em categoria textual.

        Ex:
          72 → pt-BR='quente', es='caliente'
          45 → pt-BR='morno',  es='tibio'
          15 → pt-BR='frio',   es='frio'
        """
        ...

    @abstractmethod
    def get_score_ranges(self) -> Dict[str, tuple]:
        """Retorna dicionário {categoria: (min, max)}.

        Ex:
          {'hot': (70, 100), 'warm': (40, 69), 'cold': (0, 39)}
        """
        ...

    # ── Status do pipeline ────────────────────────────────────────────────

    @abstractmethod
    def get_status_label(self, status_key: str) -> str:
        """Mapeia chave canônica → label de status no locale.

        Ex:
          'new'          → pt-BR='novo'
          'enriched'     → pt-BR='enriquecido'
          'message_sent' → pt-BR='mensagem_enviada'
        """
        ...

    @abstractmethod
    def get_statuses(self) -> Dict[str, str]:
        """Todos os status do pipeline no locale atual."""
        ...

    # ── Fallbacks e mensagens ────────────────────────────────────────────

    @abstractmethod
    def get_fallback(self, key: str) -> str:
        """Retorna string fallback localizada para chave canônica.

        Ex:
          'unknown_establishment' → pt-BR='Estabelecimento desconhecido'
          'opt_out_message'       → pt-BR='\\n\\nResponda SAIR para não receber mais contatos.'
        """
        ...

    # ── SkepticAgent ─────────────────────────────────────────────────────

    @abstractmethod
    def get_markers(self, marker_type: str) -> List[str]:
        """Marcadores textuais para heurísticas do SkepticAgent.

        marker_type:
          'generic_phrases'  → frases genéricas (H2)
          'social_absence'   → indicadores de ausência social (H6)
          'emotion_anger'    → marcadores de raiva (H7)
          'emotion_sadness'  → marcadores de tristeza (H7)
          'emotion_joy'      → marcadores de alegria (H7)
          'emotion_fear'     → marcadores de medo (H7)
        """
        ...

    @abstractmethod
    def get_language_markers(self) -> Dict[str, List[str]]:
        """Para H4 (language deviation): pares (código, [marcadores]).

        Ex:
          {
              'pt': ['o ', 'a ', 'de ', 'para ', 'com ', 'do ', 'da '],
              'en': ['the ', 'and ', 'is ', 'to ', 'of ', 'for ', 'with '],
          }
        """
        ...

    # ── Parsing (section detection keywords) ─────────────────────────────

    @abstractmethod
    def get_parser_keywords(self, section: str) -> List[str]:
        """Palavras-chave para detectar seções no parsing de texto.

        Args:
            section: Identificador da seção.
                     'profile_summary', 'weaknesses', 'opportunities',
                     'digital_maturity'

        Returns:
            Lista de palavras-chave (lowercase) que indicam início da seção.
        """
        ...

    # ── Utilitários ──────────────────────────────────────────────────────

    @abstractmethod
    def get_json_only_suffix(self) -> str:
        """Sufixo adicionado ao final de prompts para forçar JSON.

        Ex:
          pt-BR: 'Responda APENAS com o JSON válido, sem texto adicional.'
          es:    'Responda SOLAMENTE con el JSON válido, sin texto adicional.'
          en:    'Respond ONLY with valid JSON, no additional text.'
        """
        ...
