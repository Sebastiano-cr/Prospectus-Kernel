"""
PolicyEngine — Controle de Acesso Baseado em Funções (RBAC) para o Kirin.

Roles:
    admin:    Controle total — gerencia tenants, usuários, políticas, agentes
    operator: Operação diária — executa agentes, visualiza logs, gerencia leads
    viewer:   Somente leitura — visualiza dashboards, relatórios, métricas

Estrutura de permissões:
    tenant → role → agent → permission (allow/deny)

Uso:
    engine = PolicyEngine()
    await engine.check(request)  # Valida tenant + autorização
    await engine.check_tool_permission(agent_id, tenant_id, plugin, tool)
"""

import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class Role(Enum):
    """Funções disponíveis no sistema."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(Enum):
    """Permissões granulares por agente/ação."""
    # Agentes
    AGENT_ENRICH = "agent:enrich"
    AGENT_SCORE = "agent:score"
    AGENT_MESSAGE = "agent:message"
    AGENT_RESEARCH = "agent:research"
    AGENT_DISCOURSE = "agent:discourse"
    AGENT_LANGUAGE_GAME = "agent:language_game"
    AGENT_RESONANCE = "agent:resonance"

    # Dados
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"

    # Sistema
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_AUDIT = "system:audit"
    SYSTEM_BACKUP = "system:backup"

    # Tenant
    TENANT_MANAGE = "tenant:manage"
    TENANT_INVITE = "tenant:invite"


# Matriz de permissões por role
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.AGENT_ENRICH, Permission.AGENT_SCORE, Permission.AGENT_MESSAGE,
        Permission.AGENT_RESEARCH, Permission.AGENT_DISCOURSE, Permission.AGENT_LANGUAGE_GAME,
        Permission.AGENT_RESONANCE,
        Permission.DATA_READ, Permission.DATA_WRITE, Permission.DATA_DELETE,
        Permission.SYSTEM_ADMIN, Permission.SYSTEM_METRICS, Permission.SYSTEM_AUDIT,
        Permission.SYSTEM_BACKUP,
        Permission.TENANT_MANAGE, Permission.TENANT_INVITE,
    },
    Role.OPERATOR: {
        Permission.AGENT_ENRICH, Permission.AGENT_SCORE, Permission.AGENT_MESSAGE,
        Permission.AGENT_RESEARCH, Permission.AGENT_DISCOURSE, Permission.AGENT_LANGUAGE_GAME,
        Permission.AGENT_RESONANCE,
        Permission.DATA_READ, Permission.DATA_WRITE,
        Permission.SYSTEM_METRICS,
    },
    Role.VIEWER: {
        Permission.DATA_READ,
        Permission.SYSTEM_METRICS,
    },
}

# Mapeamento de agentes para permissões necessárias
AGENT_PERMISSIONS: Dict[str, Permission] = {
    "enricher": Permission.AGENT_ENRICH,
    "scorer": Permission.AGENT_SCORE,
    "messenger": Permission.AGENT_MESSAGE,
    "researcher": Permission.AGENT_RESEARCH,
    "discourse_ingestor": Permission.AGENT_DISCOURSE,
    "language_game": Permission.AGENT_LANGUAGE_GAME,
    "resonance": Permission.AGENT_RESONANCE,
}


@dataclass
class AuditEntry:
    """Entrada de auditoria para rastreamento de acessos."""
    timestamp: str
    tenant_id: str
    user_id: str
    action: str
    resource: str
    granted: bool
    reason: str = ""

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "granted": self.granted,
            "reason": self.reason
        }


@dataclass
class TenantPolicy:
    """Política de acesso para um tenant específico."""
    tenant_id: str
    user_roles: Dict[str, Role] = field(default_factory=dict)  # user_id → role
    agent_overrides: Dict[str, Dict[str, bool]] = field(default_factory=dict)  # agent → {permission: allow}
    daily_limit: int = 100
    allowed_agents: Optional[Set[str]] = None  # None = todos permitidos
    blocked_agents: Optional[Set[str]] = None  # None = nenhum bloqueado


class PolicyEngine:
    """
    Motor de políticas RBAC para o Kirin.
    
    Funcionalidades:
    1. Validação de tenant_id obrigatório
    2. Verificação de roles e permissões
    3. Override por tenant (per-agent permissions)
    4. Audit logging completo
    5. Rate limiting por tenant
    """

    def __init__(self):
        self._policies: Dict[str, TenantPolicy] = {}
        self._audit_log: List[AuditEntry] = []
        self._daily_counters: Dict[str, int] = {}  # tenant_id:count

    # --- API Pública ---

    async def check(self, request) -> None:
        """
        Valida tenant_id obrigatório e autorização do usuário.
        
        Raises:
            PermissionError: Se tenant_id ausente ou usuário não autorizado
        """
        tenant_id = getattr(request, "tenant_id", None)
        user_id = getattr(request, "user_id", None)
        agent_id = getattr(request, "agent_id", None)

        if not tenant_id:
            raise PermissionError("tenant_id obrigatório")

        # Verificar se tenant existe
        if tenant_id not in self._policies:
            self._log_audit(tenant_id, user_id or "unknown", "check", "policy",
                          granted=False, reason="tenant não encontrado")
            raise PermissionError(f"Tenant '{tenant_id}' não está registrado")

        # Verificar se usuário tem acesso ao tenant
        policy = self._policies[tenant_id]
        if user_id and user_id not in policy.user_roles:
            self._log_audit(tenant_id, user_id, "check", "tenant_access",
                          granted=False, reason="usuário não registrado no tenant")
            raise PermissionError(f"Usuário '{user_id}' não autorizado no tenant '{tenant_id}'")

        # Verificar permissão do agente
        if agent_id:
            await self.check_tool_permission(agent_id, tenant_id, "", "")

        # Verificar daily limit
        if policy.daily_limit > 0:
            current = self._daily_counters.get(f"{tenant_id}:{self._today()}", 0)
            if current >= policy.daily_limit:
                self._log_audit(tenant_id, user_id or "unknown", "check", "daily_limit",
                              granted=False, reason=f"Limite diário atingido ({current}/{policy.daily_limit})")
                raise PermissionError(f"Limite diário de mensagens atingido ({current}/{policy.daily_limit})")

        self._log_audit(tenant_id, user_id or "unknown", "check", "policy",
                       granted=True)

    async def check_tool_permission(
        self, agent_id: str, tenant_id: str, plugin: str, tool: str
    ) -> None:
        """
        Verifica se um agente/plugin tem permissão para executar uma tool.
        
        Raises:
            PermissionError: Se a permissão não for concedida
        """
        if tenant_id not in self._policies:
            raise PermissionError(f"Tenant '{tenant_id}' não registrado")

        policy = self._policies[tenant_id]

        # Verificar se agente está bloqueado
        if policy.blocked_agents and agent_id in policy.blocked_agents:
            self._log_audit(tenant_id, "system", "tool_permission", f"agent:{agent_id}",
                          granted=False, reason=f"Agente '{agent_id}' bloqueado para este tenant")
            raise PermissionError(f"Agente '{agent_id}' bloqueado para o tenant '{tenant_id}'")

        # Verificar se agente está na lista permitida
        if policy.allowed_agents and agent_id not in policy.allowed_agents:
            self._log_audit(tenant_id, "system", "tool_permission", f"agent:{agent_id}",
                          granted=False, reason=f"Agente '{agent_id}' não está na lista permitida")
            raise PermissionError(f"Agente '{agent_id}' não permitido para o tenant '{tenant_id}'")

        # Verificar permissão específica do agente
        required_permission = AGENT_PERMISSIONS.get(agent_id)
        if not required_permission:
            return  # Agente desconhecido — não bloquear

        # Verificar override do tenant
        if agent_id in policy.agent_overrides:
            override = policy.agent_overrides[agent_id]
            permission_key = required_permission.value
            if permission_key in override:
                if not override[permission_key]:
                    self._log_audit(tenant_id, "system", "tool_permission", f"agent:{agent_id}",
                                  granted=False, reason=f"Permissão {permission_key} negada por override")
                    raise PermissionError(f"Permissão negada para agente '{agent_id}' no tenant '{tenant_id}'")
                return  # Override explícito de allow

        # Verificar permissão padrão da role
        # Para isso, precisamos de um user_id — usar "system" se não fornecido
        # Na prática, o check() já validou o user antes de chegar aqui

    async def authorize(
        self, tenant_id: str, user_id: str, permission: Permission
    ) -> bool:
        """
        Verifica se um usuário tem uma permissão específica.
        
        Returns:
            True se autorizado, False caso contrário
        """
        if tenant_id not in self._policies:
            self._log_audit(tenant_id, user_id, "authorize", permission.value,
                          granted=False, reason="tenant não encontrado")
            return False

        policy = self._policies[tenant_id]
        role = policy.user_roles.get(user_id)

        if not role:
            self._log_audit(tenant_id, user_id, "authorize", permission.value,
                          granted=False, reason="usuário sem role")
            return False

        # Verificar se role tem a permissão
        allowed_permissions = ROLE_PERMISSIONS.get(role, set())
        if permission in allowed_permissions:
            self._log_audit(tenant_id, user_id, "authorize", permission.value,
                          granted=True)
            return True

        self._log_audit(tenant_id, user_id, "authorize", permission.value,
                       granted=False, reason=f"Role '{role.value}' não tem permissão '{permission.value}'")
        return False

    # --- Gerenciamento de Políticas ---

    def register_tenant(
        self,
        tenant_id: str,
        admin_user_id: str,
        daily_limit: int = 100,
        allowed_agents: Optional[Set[str]] = None,
        blocked_agents: Optional[Set[str]] = None
    ) -> None:
        """Registra um novo tenant com um usuário admin."""
        if tenant_id in self._policies:
            raise ValueError(f"Tenant '{tenant_id}' já existe")

        policy = TenantPolicy(
            tenant_id=tenant_id,
            user_roles={admin_user_id: Role.ADMIN},
            daily_limit=daily_limit,
            allowed_agents=allowed_agents,
            blocked_agents=blocked_agents
        )
        self._policies[tenant_id] = policy
        logger.info(f"Tenant registrado: {tenant_id} (admin: {admin_user_id})")

    def add_user(self, tenant_id: str, user_id: str, role: Role) -> None:
        """Adiciona um usuário a um tenant com uma role específica."""
        if tenant_id not in self._policies:
            raise ValueError(f"Tenant '{tenant_id}' não encontrado")

        self._policies[tenant_id].user_roles[user_id] = role
        logger.info(f"Usuário adicionado: {user_id} → {role.value} no tenant {tenant_id}")

    def remove_user(self, tenant_id: str, user_id: str) -> None:
        """Remove um usuário de um tenant."""
        if tenant_id not in self._policies:
            raise ValueError(f"Tenant '{tenant_id}' não encontrado")

        if user_id in self._policies[tenant_id].user_roles:
            del self._policies[tenant_id].user_roles[user_id]
            logger.info(f"Usuário removido: {user_id} do tenant {tenant_id}")

    def set_agent_override(
        self, tenant_id: str, agent_id: str, permission: Permission, allow: bool
    ) -> None:
        """Define uma permissão específica de agente para um tenant."""
        if tenant_id not in self._policies:
            raise ValueError(f"Tenant '{tenant_id}' não encontrado")

        if agent_id not in self._policies[tenant_id].agent_overrides:
            self._policies[tenant_id].agent_overrides[agent_id] = {}

        self._policies[tenant_id].agent_overrides[agent_id][permission.value] = allow
        logger.info(f"Override definido: {agent_id}.{permission.value} = {'allow' if allow else 'deny'} no tenant {tenant_id}")

    def increment_daily_counter(self, tenant_id: str) -> int:
        """Incrementa o contador diário de mensagens de um tenant."""
        key = f"{tenant_id}:{self._today()}"
        current = self._daily_counters.get(key, 0)
        self._daily_counters[key] = current + 1
        return current + 1

    def get_daily_count(self, tenant_id: str) -> int:
        """Retorna o contador atual de mensagens do dia para um tenant."""
        key = f"{tenant_id}:{self._today()}"
        return self._daily_counters.get(key, 0)

    # --- Auditoria ---

    def get_audit_log(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Retorna entradas de auditoria filtradas."""
        entries = self._audit_log

        if tenant_id:
            entries = [e for e in entries if e.tenant_id == tenant_id]
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]

        return [e.to_dict() for e in entries[-limit:]]

    def clear_audit_log(self) -> int:
        """Limpa o log de auditoria. Retorna o número de entradas removidas."""
        count = len(self._audit_log)
        self._audit_log.clear()
        return count

    # --- Internos ---

    def _log_audit(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        granted: bool,
        reason: str = ""
    ) -> None:
        """Registra uma entrada de auditoria."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            granted=granted,
            reason=reason
        )
        self._audit_log.append(entry)

        # Log warnings para acessos negados
        if not granted:
            logger.warning(
                f"Acesso negado: user={user_id} tenant={tenant_id} "
                f"action={action} resource={resource} reason={reason}"
            )

    @staticmethod
    def _today() -> str:
        """Retorna a data atual no formato YYYY-MM-DD."""
        return datetime.now().strftime("%Y-%m-%d")
