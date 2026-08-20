from typing import List, Dict, Any, Type
from pydantic import BaseModel

class Skill(BaseModel):
    name: str
    description: str
    tools: List[str]
    triggers: List[str]
    default_permissions: Dict[str, str]
    
    class Config:
        arbitrary_types_allowed = True

class SkillRegistry:
    _skills: Dict[str, Skill] = {}

    @classmethod
    def register(cls, skill: Skill):
        cls._skills[skill.name] = skill

    @classmethod
    def get_all(cls) -> List[Skill]:
        return list(cls._skills.values())

    @classmethod
    def get_skill(cls, name: str) -> Skill:
        return cls._skills.get(name)
