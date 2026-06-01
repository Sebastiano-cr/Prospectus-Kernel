from core.agents.base_agent import BaseAgent


class CRMAgent(BaseAgent):
    _context_key = "lead"
    _action = "crm_sync"
    _data_key = "lead"
    _endpoint = "/crm_sync"
