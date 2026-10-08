"""Deterministic baseline action planner; an LLM provider can be layered above it."""
from __future__ import annotations
from dataclasses import dataclass,field
import uuid
@dataclass
class PlannedStep:
    step_id:str; tool_name:str; parameters:dict; depends_on:list[str]=field(default_factory=list); description:str=""
@dataclass
class ActionPlan:
    plan_id:str; intent:str; steps:list[PlannedStep]; estimated_risk:str
class ActionPlanner:
    def plan(self,intent):
        x=intent.lower(); steps=[]
        if "slow" in x or "performance" in x:
            for i,name in enumerate(["get_system_info","get_cpu_usage","get_memory_usage","get_disk_usage","list_processes"],1):
                steps.append(PlannedStep(str(i),name,{},description=name.replace("_"," ").title()))
        elif "process" in x or "running" in x: steps=[PlannedStep("1","list_processes",{},description="List running processes")]
        elif "disk" in x or "storage" in x: steps=[PlannedStep("1","get_disk_usage",{},description="Check disk usage")]
        elif "memory" in x or "ram" in x: steps=[PlannedStep("1","get_memory_usage",{},description="Check memory usage")]
        elif "cpu" in x: steps=[PlannedStep("1","get_cpu_usage",{},description="Check CPU usage")]
        else: steps=[PlannedStep("1","get_system_info",{},description="Get system information")]
        risk="high" if any(s.tool_name in {"execute_command","restart_service","terminate_process"} for s in steps) else "medium" if any(s.tool_name in {"list_files","read_file","list_processes"} for s in steps) else "low"
        return ActionPlan(str(uuid.uuid4()),intent,steps,risk)
