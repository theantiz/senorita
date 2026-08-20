from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToneStyle(BaseModel):
    emoji: Literal["none", "rare", "occasional", "frequent"] = "occasional"
    sentence_length: Literal["short", "medium", "long"] = "medium"
    punctuation: Literal["minimal", "standard", "heavy"] = "standard"
    uses_exclamation: bool = False
    uses_lowercase: bool = False
    uses_bullet_lists: bool = False
    uses_questions: Literal["rare", "occasional", "often"] = "occasional"
    uses_abbreviations: list[str] = Field(default_factory=list)


class ToneRelationship(BaseModel):
    warmth: Literal["low", "medium", "high"] = "medium"
    professionalism: Literal["low", "medium", "high"] = "medium"
    directness: Literal["low", "medium", "high"] = "medium"


class ReusablePattern(BaseModel):
    intent: str
    template: str


class ChannelToneProfile(BaseModel):
    version: int = 1
    updated_at: datetime | None = None
    computed_at: datetime | None = None
    user_override: bool = False
    confidence: float = 0.0
    sample_count: int = 0

    style: ToneStyle = Field(default_factory=ToneStyle)
    relationship: ToneRelationship = Field(default_factory=ToneRelationship)

    greeting_examples: list[str] = Field(default_factory=list)
    closing_examples: list[str] = Field(default_factory=list)
    reusable_patterns: list[ReusablePattern] = Field(default_factory=list)


# A dictionary mapping channel name (e.g., "email", "slack") to its profile
# We keep it as a dict in Pydantic so we can add arbitrary channels easily.
ToneProfileDict = dict[str, ChannelToneProfile]


class ContactBase(BaseModel):
    name: str
    relationship_type: str
    tone_profile: dict = Field(default_factory=dict)
    last_discussed_topic: str | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: str | None = None
    relationship_type: str | None = None
    tone_profile: dict | None = None
    last_discussed_topic: str | None = None


class ContactRead(ContactBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
