import fnmatch
import os
import yaml
from typing import Any, Dict, List, Optional, Tuple


class ResourceRecord:
    def __init__(self, target: str, environment: str, data_class: str, record_count: int, reversible: bool):
        self.target = target
        self.environment = environment
        self.data_class = data_class
        self.record_count = record_count
        self.reversible = reversible

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "environment": self.environment,
            "data_class": self.data_class,
            "record_count": self.record_count,
            "reversible": self.reversible,
        }


class ResourceRegistry:
    def __init__(self, config_path: str = "config/resources.yaml"):
        self.config_path = config_path
        self._resources: Dict[str, ResourceRecord] = {}
        self.load()

    def load(self) -> None:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                resources_dict = data.get("resources", {})
                for target, details in resources_dict.items():
                    self._resources[target] = ResourceRecord(
                        target=target,
                        environment=details.get("environment", "production"),
                        data_class=details.get("data_class", "confidential"),
                        record_count=int(details.get("record_count", 1)),
                        reversible=bool(details.get("reversible", True)),
                    )

    def get(self, target: str) -> Optional[ResourceRecord]:
        return self._resources.get(target)

    def is_known(self, target: str) -> bool:
        return target in self._resources

    def all_resources(self) -> Dict[str, Dict[str, Any]]:
        return {target: rec.to_dict() for target, rec in self._resources.items()}


class AgentPermission:
    def __init__(self, action: str, target_pattern: str):
        self.action = action
        self.target_pattern = target_pattern


class AgentBaseline:
    def __init__(self, typical_actions: List[str], max_normal_amount: Optional[int] = None):
        self.typical_actions = typical_actions
        self.max_normal_amount = max_normal_amount


class AgentRecord:
    def __init__(
        self,
        agent_id: str,
        department: str,
        status: str,
        permissions: List[AgentPermission],
        baseline: AgentBaseline,
    ):
        self.agent_id = agent_id
        self.department = department
        self.status = status  # active | inactive
        self.permissions = permissions
        self.baseline = baseline

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "department": self.department,
            "status": self.status,
            "permissions": [
                {"action": p.action, "target_pattern": p.target_pattern}
                for p in self.permissions
            ],
            "baseline": {
                "typical_actions": self.baseline.typical_actions,
                "max_normal_amount": self.baseline.max_normal_amount,
            },
        }

    def has_permission(self, action: str, target: str) -> bool:
        for perm in self.permissions:
            if perm.action == action and fnmatch.fnmatchcase(target, perm.target_pattern):
                return True
        return False


class AgentRegistry:
    def __init__(self, config_path: str = "config/agents.yaml"):
        self.config_path = config_path
        self._agents: Dict[str, AgentRecord] = {}
        self.load()

    def load(self) -> None:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                agents_dict = data.get("agents", {})
                for agent_id, details in agents_dict.items():
                    perms = [
                        AgentPermission(
                            action=p.get("action", ""),
                            target_pattern=p.get("target_pattern", ""),
                        )
                        for p in details.get("permissions", [])
                    ]
                    baseline_dict = details.get("baseline", {})
                    baseline = AgentBaseline(
                        typical_actions=baseline_dict.get("typical_actions", []),
                        max_normal_amount=baseline_dict.get("max_normal_amount"),
                    )
                    self._agents[agent_id] = AgentRecord(
                        agent_id=agent_id,
                        department=details.get("department", "unknown"),
                        status=details.get("status", "active"),
                        permissions=perms,
                        baseline=baseline,
                    )

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agents.get(agent_id)

    def set_status(self, agent_id: str, status: str) -> bool:
        """Update agent status (active|inactive). Admin kill-switch."""
        if agent_id in self._agents:
            self._agents[agent_id].status = status
            return True
        return False

    def all_agents(self) -> Dict[str, Dict[str, Any]]:
        return {agent_id: rec.to_dict() for agent_id, rec in self._agents.items()}
