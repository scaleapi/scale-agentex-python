"""Pydantic models for the D&D character builder."""

from __future__ import annotations

from pydantic import BaseModel, Field

VALID_CLASSES = ["Fighter", "Wizard", "Cleric", "Rogue", "Ranger"]
CASTER_CLASSES = ["Wizard", "Cleric"]

WIZARD_SPELLS = [
    "Fire Bolt",
    "Mage Hand",
    "Prestidigitation",
    "Magic Missile",
    "Shield",
    "Mage Armor",
    "Sleep",
    "Burning Hands",
    "Detect Magic",
    "Thunderwave",
]

CLERIC_SPELLS = [
    "Sacred Flame",
    "Guidance",
    "Thaumaturgy",
    "Cure Wounds",
    "Healing Word",
    "Guiding Bolt",
    "Bless",
    "Shield of Faith",
    "Inflict Wounds",
    "Command",
]

HIT_DIE = {"Fighter": 10, "Wizard": 6, "Cleric": 8, "Rogue": 8, "Ranger": 10}


class CharacterSheet(BaseModel):
    """A Level 1 D&D character sheet, built incrementally."""

    name: str | None = None
    character_class: str | None = None
    strength: int | None = None
    dexterity: int | None = None
    constitution: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    charisma: int | None = None
    hp: int | None = None
    ac: int | None = None
    spells: list[str] = Field(default_factory=list)

    def __str__(self) -> str:
        """Render the full character sheet, showing blanks for unfilled fields."""
        blank = "___"
        s = lambda v: str(v) if v is not None else blank  # noqa: E731
        spells = "".join(f"\n  - {spell}" for spell in self.spells).strip() if self.spells else blank
        return f"""\
═══ CHARACTER SHEET ═══
Name:  {self.name or blank}
Class: {self.character_class or blank}
HP:    {s(self.hp)}
AC:    {s(self.ac)}

Ability Scores:
  STR {s(self.strength):>3}  DEX {s(self.dexterity):>3}
  INT {s(self.intelligence):>3}  WIS {s(self.wisdom):>3}
  CON {s(self.constitution):>3}  CHA {s(self.charisma):>3}

Spells:
{spells}
══════════════════════"""


class Step(BaseModel):
    """Tracks a single step in the character building process."""

    name: str
    agent_name: str
    is_done: bool = False

    def __str__(self) -> str:
        """Render step as a checklist item."""
        mark = "x" if self.is_done else " "
        return f"[{mark}] {self.name}"


DEFAULT_STEPS = [
    Step(name="Name", agent_name="name_agent"),
    Step(name="Class", agent_name="class_agent"),
    Step(name="Ability Scores", agent_name="ability_scores_agent"),
    Step(name="Spells", agent_name="spells_agent"),
]


class StateModel(BaseModel):
    """Persisted state for AgentEx across conversation turns."""

    input_list: list[dict]
    sheet: dict
    steps: list[dict]
    last_agent_name: str
