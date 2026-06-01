from core.agents.base_agent import BaseAgent, InvokeRequest


class ScoreAgent(BaseAgent):
    _context_key = "dossie"
    _action = "score"
    _data_key = "dossie"
    _endpoint = "/score"
