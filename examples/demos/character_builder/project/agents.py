"""Agent definitions, tools, and orchestrator for the D&D character builder."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentex.lib.utils.logging import make_logger
from agents import Agent, RunContextWrapper, function_tool, handoff

from project.models import (
    CASTER_CLASSES,
    CLERIC_SPELLS,
    DEFAULT_STEPS,
    HIT_DIE,
    VALID_CLASSES,
    WIZARD_SPELLS,
    CharacterSheet,
    Step,
)

if TYPE_CHECKING:
    from agents import Model

logger = make_logger(__name__)


# ── Shared context ──────────────────────────────────────────────────────────────────────────────────


@dataclass
class BuilderContext:
    """Mutable state shared across all agents."""

    sheet: CharacterSheet = field(default_factory=CharacterSheet)
    steps: list[Step] = field(default_factory=lambda: [s.model_copy() for s in DEFAULT_STEPS])

    def mark_step_done(self, agent_name: str) -> None:
        """Flag a step as completed by agent name."""
        for step in self.steps:
            if step.agent_name == agent_name:
                step.is_done = True
                return

    def next_step(self) -> Step | None:
        """Return the next incomplete step."""
        return next((s for s in self.steps if not s.is_done), None)


# ── Agents ──────────────────────────────────────────────────────────────────────────────────────────

_ORCHESTRATOR_NAME = "character_builder_orchestrator"
_HANDOFF_BACK = "transfer_to_character_builder_orchestrator()"

SPELL_LISTS: dict[str, list[str]] = {"Wizard": WIZARD_SPELLS, "Cleric": CLERIC_SPELLS}

# ── Name agent ──────────────────────────────────────────────────────────────────────────────────────


@function_tool
def finalize_name(ctx: RunContextWrapper[BuilderContext], name: str) -> str:
    """Finalize the character's name.

    Args:
        ctx: Injected by SDK.
        name: The character's full name.

    """
    logger.info("finalize_name: %r", name)
    ctx.context.sheet.name = name
    ctx.context.mark_step_done("name_agent")
    return f"SUCCESS — name set. Now call {_HANDOFF_BACK} to continue.\n\n{ctx.context.sheet}"


# ── Class agent ─────────────────────────────────────────────────────────────────────────────────────


@function_tool
def finalize_class(ctx: RunContextWrapper[BuilderContext], character_class: str) -> str:
    """Finalize the character's class.

    Args:
        ctx: Injected by SDK.
        character_class: One of the five valid classes.

    """
    logger.info("finalize_class: %r", character_class)
    if character_class not in VALID_CLASSES:
        return f"Invalid class '{character_class}'. Choose from: {', '.join(VALID_CLASSES)}"
    ctx.context.sheet.character_class = character_class
    ctx.context.mark_step_done("class_agent")

    # If not a caster, skip the spells step
    if character_class not in CASTER_CLASSES:
        ctx.context.mark_step_done("spells_agent")

    return f"SUCCESS — class set. Now call {_HANDOFF_BACK} to continue.\n\n{ctx.context.sheet}"


# ── Ability scores agent ────────────────────────────────────────────────────────────────────────────


@function_tool
def roll_ability_score() -> str:
    """Roll 4d6 and drop the lowest die.

    Returns:
        The four dice rolled and the resulting score.

    """
    rolls = sorted([random.randint(1, 6) for _ in range(4)], reverse=True)  # noqa: S311
    total = sum(rolls[:3])
    logger.info("roll_ability_score: rolls=%s total=%d", rolls, total)
    return f"Rolled {rolls} → kept top 3 → {total}"


@function_tool
def finalize_ability_scores(
    ctx: RunContextWrapper[BuilderContext],
    strength: int,
    dexterity: int,
    constitution: int,
    intelligence: int,
    wisdom: int,
    charisma: int,
) -> str:
    """Finalize all six ability scores and compute HP and AC.

    Args:
        ctx: Injected by SDK.
        strength: Strength score (3-18).
        dexterity: Dexterity score (3-18).
        constitution: Constitution score (3-18).
        intelligence: Intelligence score (3-18).
        wisdom: Wisdom score (3-18).
        charisma: Charisma score (3-18).

    """
    logger.info(
        "finalize_ability_scores: STR=%d DEX=%d CON=%d INT=%d WIS=%d CHA=%d",
        strength,
        dexterity,
        constitution,
        intelligence,
        wisdom,
        charisma,
    )
    sheet = ctx.context.sheet
    sheet.strength = strength
    sheet.dexterity = dexterity
    sheet.constitution = constitution
    sheet.intelligence = intelligence
    sheet.wisdom = wisdom
    sheet.charisma = charisma

    # HP: hit die max + CON modifier at level 1
    con_mod = (constitution - 10) // 2
    sheet.hp = HIT_DIE.get(sheet.character_class or "Fighter", 8) + con_mod

    # AC: base 10 + DEX modifier
    sheet.ac = 10 + (dexterity - 10) // 2

    ctx.context.mark_step_done("ability_scores_agent")
    return f"Ability scores set!\n\n{ctx.context.sheet}"


# ── Spells agent ────────────────────────────────────────────────────────────────────────────────────


@function_tool
def finalize_spells(ctx: RunContextWrapper[BuilderContext], spells: list[str]) -> str:
    """Finalize the character's spell selection.

    Args:
        ctx: Injected by SDK.
        spells: List of spell names chosen by the player.

    """
    logger.info("finalize_spells: %s", spells)
    cls = ctx.context.sheet.character_class
    if not cls:
        return "No class set in character sheet"
    valid_spells = SPELL_LISTS.get(cls, [])

    invalid = [s for s in spells if s not in valid_spells]
    if invalid:
        return f"Invalid spells for {cls}: {', '.join(invalid)}. Choose from: {', '.join(valid_spells)}"

    ctx.context.sheet.spells = spells
    ctx.context.mark_step_done("spells_agent")
    return f"SUCCESS — spells finalized. Now call {_HANDOFF_BACK} to continue.\n\n{ctx.context.sheet}"


def _spells_instructions(ctx: RunContextWrapper[BuilderContext], _agent: Agent[BuilderContext]) -> str:
    cls = ctx.context.sheet.character_class or "Unknown"
    spells = chr(10).join(f"- {s}" for s in SPELL_LISTS.get(cls, []))

    return f"""\
You help the user choose spells for their Level 1 {cls}.

Available spells for {cls}:
{spells}

The user should pick 3-4 spells from the list above.
Help them understand what each spell does if asked.
When decided, call finalize_spells() then hand back via {_HANDOFF_BACK}.
"""


# ── Orchestrator ────────────────────────────────────────────────────────────────────────────────────


def _orchestrator_instructions(ctx: RunContextWrapper[BuilderContext], _agent: Agent[BuilderContext]) -> str:
    bc = ctx.context
    progress = "\n".join(str(s) for s in bc.steps)

    rules = [
        "NEVER answer D&D questions yourself - hand off to the appropriate agent.",
        "NEVER skip steps or go backwards.",
    ]

    if not any(s.is_done for s in bc.steps):
        rules.append("This is a NEW session. Greet the user and IMMEDIATELY hand off to `name_agent`.")
    elif all(s.is_done for s in bc.steps):
        rules.append("ALL steps are complete! Congratulate the user and present their character.")
    else:
        nxt = bc.next_step()
        if nxt:
            rules.append(f"Hand off to `{nxt.agent_name}` for the next step: {nxt.name}.")

    rule_lines = chr(10).join(f"- {r}" for r in rules)
    return f"""\
You are the orchestrator for a D&D character builder.
You guide the user through building a Level 1 character by handing off to specialized step agents.

<progress>
{progress}
</progress>

<rules>
{rule_lines}
</rules>
"""


# ── Build agent graph ───────────────────────────────────────────────────────────────────────────────


def build_agents(model: Model) -> tuple[Agent, dict[str, Agent]]:
    """Build the orchestrator and all sub-agents sharing a single Model instance.

    The model must be a concrete Model instance (not a string) so that all agents
    reuse the same provider/client across handoffs.
    """
    name_agent = Agent(
        name="name_agent",
        instructions=f"""\
You help the user choose a name for their D&D character.

Ask what they'd like to name their character.
When they provide a name, call finalize_name() then hand back to the orchestrator via {_HANDOFF_BACK}.
""",
        model=model,
        tools=[finalize_name],
    )

    class_agent = Agent(
        name="class_agent",
        instructions=f"""\
You help the user choose a class for their D&D character.

Available classes: Fighter, Wizard, Cleric, Rogue, Ranger.

Brief descriptions:
- Fighter: Martial combat masters, tough and versatile.
- Wizard: Arcane spellcasters who learn magic through study.
- Cleric: Divine spellcasters channeling their deity's power.
- Rogue: Stealthy experts in precision strikes and tricks.
- Ranger: Wilderness warriors skilled in tracking and archery.

When they choose, call finalize_class() then hand back via {_HANDOFF_BACK}.
""",
        model=model,
        tools=[finalize_class],
    )

    ability_scores_agent = Agent(
        name="ability_scores_agent",
        instructions=f"""\
You help the user determine their six ability scores:
Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma.

Roll for scores using roll_ability_score() (4d6 drop lowest).
Roll 6 times, then help the user assign each result to an ability.

Walk them through:
1. Roll 6 scores using roll_ability_score().
2. Present the 6 results.
3. Suggest a good arrangement for their class.
4. Once confirmed, call finalize_ability_scores().
5. Hand back via {_HANDOFF_BACK}.
""",
        model=model,
        tools=[roll_ability_score, finalize_ability_scores],
    )

    spells_agent = Agent(
        name="spells_agent",
        instructions=_spells_instructions,
        model=model,
        tools=[finalize_spells],
    )

    step_agents = [name_agent, class_agent, ability_scores_agent, spells_agent]

    orch = Agent(
        name=_ORCHESTRATOR_NAME,
        instructions=_orchestrator_instructions,
        model=model,
        handoffs=[handoff(agent=a) for a in step_agents],
    )

    for a in step_agents:
        a.handoffs = [handoff(agent=orch)]

    agents_by_name: dict[str, Agent] = {orch.name: orch, **{a.name: a for a in step_agents}}
    return orch, agents_by_name
