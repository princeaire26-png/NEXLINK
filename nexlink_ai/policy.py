"""Policy engine for safe AI tool execution."""
from __future__ import annotations
from dataclasses import dataclass
from .tools import RiskLevel
@dataclass
class PolicyContext:
    user_id:str; device_id:str; session_id:str; permissions:list[str]; role:str
@dataclass
class PolicyDecision:
    decision:str; reason:str=""
class PolicyEngine:
    def __init__(self,max_auto_risk=RiskLevel.LOW,allow_high_risk=True,allow_critical=False):
        self.max_auto_risk=max_auto_risk; self.allow_high_risk=allow_high_risk; self.allow_critical=allow_critical
    def evaluate(self,tool_name,risk_level,required_permissions,context):
        order={RiskLevel.LOW:0,RiskLevel.MEDIUM:1,RiskLevel.HIGH:2,RiskLevel.CRITICAL:3}
        if risk_level==RiskLevel.CRITICAL and not self.allow_critical:return PolicyDecision("deny",f"Critical-risk tool '{tool_name}' is not permitted")
        if risk_level==RiskLevel.HIGH and not self.allow_high_risk:return PolicyDecision("deny",f"High-risk tool '{tool_name}' is not permitted")
        for perm in required_permissions:
            if perm not in context.permissions and context.role!="owner":return PolicyDecision("deny",f"Missing required permission: {perm}")
        if order[risk_level]>order[self.max_auto_risk]:return PolicyDecision("require_authorization",f"Tool '{tool_name}' requires explicit authorization")
        return PolicyDecision("allow")
