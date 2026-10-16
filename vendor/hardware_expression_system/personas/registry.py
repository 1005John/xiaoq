"""Persona profiles for character and style selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaProfile:
    id: str
    name: str
    agent_id: str | None
    character_id: str
    face_style_id: str
    voice_id: str | None
    default_state: str
    default_mood: str
    renderer_profile: str
    notes: str


DEFAULT_PERSONAS = (
    PersonaProfile(
        id="mobilework_bluebot",
        name="MobileWork Bluebot",
        agent_id="mobilework",
        character_id="bluebot",
        face_style_id="oled-soft",
        voice_id=None,
        default_state="IDLE",
        default_mood="focused",
        renderer_profile="bluebot_oled_1280x720",
        notes="Bluebot is the visible carrier of the MobileWork AI agent.",
    ),
    PersonaProfile(
        id="xiaoq_brand_mascot",
        name="XiaoQ Brand Mascot",
        agent_id=None,
        character_id="xiaoq",
        face_style_id="cute",
        voice_id="soda",
        default_state="IDLE",
        default_mood="happy",
        renderer_profile="xiaoq_cute_1280x720",
        notes="The cute style is based on the company mascot XiaoQ.",
    ),
    PersonaProfile(
        id="xiaoq_neon_analyst",
        name="XiaoQ Neon Analyst",
        agent_id=None,
        character_id="xiaoq",
        face_style_id="neon",
        voice_id="bingtang",
        default_state="IDLE",
        default_mood="focused",
        renderer_profile="xiaoq_neon_1280x720",
        notes="Compatibility profile from the latest XiaoQ product.",
    ),
)


class PersonaRegistry:
    def __init__(self, profiles: tuple[PersonaProfile, ...] = DEFAULT_PERSONAS) -> None:
        self._profiles = {profile.id: profile for profile in profiles}

    def get(self, persona_id: str) -> PersonaProfile:
        try:
            return self._profiles[persona_id]
        except KeyError as exc:
            raise KeyError(f"Unknown persona: {persona_id}") from exc

    def all(self) -> tuple[PersonaProfile, ...]:
        return tuple(self._profiles.values())

    def character_style(self, persona_id: str) -> tuple[str, str]:
        profile = self.get(persona_id)
        return profile.character_id, profile.face_style_id
