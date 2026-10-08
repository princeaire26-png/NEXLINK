"""Provider-neutral AI interface; no provider is required for NEXLINK core operation."""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import Enum
class Role(str,Enum): SYSTEM="system"; USER="user"; ASSISTANT="assistant"; TOOL="tool"
@dataclass
class Message: role:Role; content:str; tool_call_id:str|None=None
@dataclass
class ToolSpec: name:str; description:str; parameters:dict
@dataclass
class ToolCall: id:str; name:str; arguments:dict
@dataclass
class UsageInfo: prompt_tokens:int=0; completion_tokens:int=0; total_tokens:int=0
@dataclass
class ProviderResponse: content:str; tool_calls:list[ToolCall]=field(default_factory=list); finish_reason:str="stop"; usage:UsageInfo=field(default_factory=UsageInfo)
class AiProvider:
    name="base"
    async def generate(self,messages,tools): raise NotImplementedError
    async def is_available(self): return False
class MockProvider(AiProvider):
    name="mock"
    async def generate(self,messages,tools): return ProviderResponse("Mock response")
    async def is_available(self): return True
