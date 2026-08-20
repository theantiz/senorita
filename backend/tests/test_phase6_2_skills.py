import pytest
from app.agents.skills.base import SkillRegistry
import app.agents.skills

def test_skills_registered():
    skills = SkillRegistry.get_all()
    assert len(skills) >= 3
    skill_names = [s.name for s in skills]
    assert "MeetingSkill" in skill_names
    assert "EmailSkill" in skill_names
    assert "TaskSkill" in skill_names

