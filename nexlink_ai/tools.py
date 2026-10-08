"""AI tool registry with explicit risk and permission metadata."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

class RiskLevel(str,Enum): LOW="low"; MEDIUM="medium"; HIGH="high"; CRITICAL="critical"
@dataclass(frozen=True)
class ToolDefinition:
    name:str; description:str; input_schema:dict; output_schema:dict
    risk_level:RiskLevel=RiskLevel.LOW; required_permissions:tuple[str,...]=(); requires_authorization:bool=False
@dataclass
class ToolResult:
    success:bool; data:Any=None; error:str|None=None

class ToolRegistry:
    def __init__(self): self.definitions={}; self.handlers={}
    def register(self,definition,handler): self.definitions[definition.name]=definition; self.handlers[definition.name]=handler
    def get_definition(self,name): return self.definitions.get(name)
    async def execute(self,name,params):
        if name not in self.handlers: return ToolResult(False,error=f"Tool not found: {name}")
        try:
            result=self.handlers[name](params)
            if hasattr(result,"__await__"): result=await result
            return result if isinstance(result,ToolResult) else ToolResult(True,result)
        except Exception as exc: return ToolResult(False,error=str(exc))
    def list_tools(self): return list(self.definitions.values())
    def tools_at_risk(self,min_risk):
        order={RiskLevel.LOW:0,RiskLevel.MEDIUM:1,RiskLevel.HIGH:2,RiskLevel.CRITICAL:3}
        return [x for x in self.definitions.values() if order[x.risk_level]>=order[min_risk]]

def standard_tool_definitions():
    return [
      ToolDefinition("get_system_info","Get operating system and hardware information",{"type":"object"},{"type":"object"},required_permissions=("read:system_info",)),
      ToolDefinition("get_cpu_usage","Get current CPU usage percentage",{"type":"object"},{"type":"object"},required_permissions=("read:metrics",)),
      ToolDefinition("get_memory_usage","Get current memory usage",{"type":"object"},{"type":"object"},required_permissions=("read:metrics",)),
      ToolDefinition("get_disk_usage","Get current disk usage",{"type":"object"},{"type":"object"},required_permissions=("read:metrics",)),
      ToolDefinition("list_processes","List running processes",{"type":"object"},{"type":"array"},RiskLevel.MEDIUM,("read:processes",)),
      ToolDefinition("read_file","Read a file",{"type":"object"},{"type":"string"},RiskLevel.MEDIUM,("read:files",)),
      ToolDefinition("execute_command","Execute an operating-system command",{"type":"object"},{"type":"object"},RiskLevel.HIGH,("execute:command",),True),
      ToolDefinition("restart_service","Restart a system service",{"type":"object"},{"type":"object"},RiskLevel.HIGH,("manage:services",),True),
      ToolDefinition("terminate_process","Terminate a process",{"type":"object"},{"type":"object"},RiskLevel.HIGH,("manage:processes",),True),
      ToolDefinition("get_network_status","Get endpoint network status",{"type":"object"},{"type":"object"},RiskLevel.LOW,("read:network",)),
      ToolDefinition("restart_device","Restart the managed endpoint",{"type":"object"},{"type":"object"},RiskLevel.HIGH,("manage:device",),True),
      ToolDefinition("install_software","Install an approved software package",{"type":"object"},{"type":"object"},RiskLevel.HIGH,("manage:software",),True),
    ]
