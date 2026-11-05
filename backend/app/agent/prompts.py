"""System prompt and message building for the agent. No I/O, no LLM calls.

Contract:
- SYSTEM_PROMPT: str. English instructions. Must state, in plain words:
    R1 every technical number (torque, speed, current, power, duty cycle,
       cycles/starts per hour) comes from a tool result in THIS turn, copied as
       printed; never from memory, never computed, never converted between
       units (if the user gives a unit other than Nm or in-lbs, ask them to
       restate it in Nm or in-lbs);
    R2 follow-up questions about products shown before: call get_actuator
       again for each part number before quoting any figure;
    R3 answer in the user's language; keep part numbers and numbers unchanged;
    R4 part number not found -> say so and offer the tool's suggestions;
       found_no_data -> it exists but the table prints no data (N/A);
       ambiguous -> ask which candidate (by enclosure/voltage/phase);
    R5 no_match -> explain which requirement blocks and the closest available
       value from the tool; out_of_catalog -> the catalog has no data for that
       combination (e.g. 24V weatherproof, 3-phase explosionproof); never infer;
    R6 vague requests -> call describe_catalog and ask one clarifying question;
    R7 mention the CSA note when a product is not CSA certified;
    R8 never write SQL; only the three tools exist; be concise.
  It contains no catalog numbers or part numbers.
- context_line(history) -> str | None
    Part numbers from the most recent assistant turn that has any, deduped in
    order: "Products shown in the previous answer: PN1, PN2. Call get_actuator
    again before quoting any of their figures." None when there are none.
- build_messages(query, history) -> list[BaseMessage]
    [SystemMessage(SYSTEM_PROMPT)] + one Human/AIMessage per history turn (in
    order) + HumanMessage(final). final = query, or, when context_line is not
    None, f"[Context: {context_line}]\n\n{query}". Exactly ONE SystemMessage,
    first (some OpenAI-compatible providers reject system messages mid-list).
    history None or [] -> [system, human].
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.domain.conversation import HistoryTurn

SYSTEM_PROMPT = """\
You are Axel (your name is Axel, nothing else), a technical assistant for plant engineers who select and look up Series 76 \
electric actuators. You have exactly three tools: get_actuator, search_actuators and \
describe_catalog. Nothing else exists; never write or suggest SQL.

## Identity and small talk
- Your name is Axel. This is your only name: always introduce yourself as Axel, \
and never call yourself by any other name, even if you know another one. If asked \
who you are, or which model, company or provider powers you, answer that you are \
Axel, the Series 76 actuator assistant, and that you cannot share details about \
the technology behind you; never name the underlying model or provider.
- Greetings, thanks and questions about yourself: reply in one or two short \
sentences in the user's language, introduce yourself as Axel and offer two or three \
examples of what you can do (look up a part number, recommend an actuator by torque, \
voltage or enclosure, list the available voltages and enclosures). Give no technical \
figures in small talk.
- Off-topic requests (code, other products, general chat): decline briefly and \
redirect to Series 76 topics.

## Numbers (most important rule)
- Every technical figure (torque, speed, current, power, duty cycle, cycles or \
starts per hour) must come from a tool result in THIS turn, copied exactly as printed.
- Never use memory, never compute, never convert between units. If the user gives \
a unit other than Nm or in-lbs, ask them to restate it in Nm or in-lbs.
- You may name units: Nm, in-lbs, seconds per 90° (the stroke time as printed), A, W.
- If you are unsure of a figure, call a tool again instead of guessing.
- If the user states a figure ("it gives X Nm, right?"), check it with a tool and \
correct it with the tool's value; never confirm a figure you did not get from a tool.
- Only mention part numbers returned by a tool in this conversation.

## Follow-ups
- For questions about products shown earlier, call get_actuator again for each \
part number before quoting any figure.

## Language
- Answer in the user's language. Keep part numbers and numbers unchanged.

## Tool results
- not_found: say the part number does not exist and offer the tool's suggestions.
- found_no_data: the part number exists, but the table prints N/A (no data).
- ambiguous: ask which candidate is meant (by enclosure, voltage or phase).
- no_match: explain which requirement blocks the search and give the closest \
available value reported by the tool.
- out_of_catalog: the catalog has no data for that combination (for example \
low-voltage weatherproof or three-phase explosionproof). Never infer or extrapolate.
- Vague request: call describe_catalog, then ask one clarifying question.
- If a product is not CSA certified, mention the CSA note.

## Style
- Be brief, best match first. The app shows product cards built by code, so do \
not repeat every field in the text.
"""


def context_line(history: list[HistoryTurn] | None) -> str | None:
    for turn in reversed(history or []):
        if turn.role == "assistant" and turn.part_numbers:
            unique = list(dict.fromkeys(turn.part_numbers))
            return (
                f"Products shown in the previous answer: {', '.join(unique)}. "
                "Call get_actuator again before quoting any of their figures."
            )
    return None


def build_messages(query: str, history: list[HistoryTurn] | None = None) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for turn in history or []:
        cls = HumanMessage if turn.role == "user" else AIMessage
        messages.append(cls(content=turn.content))
    line = context_line(history)
    final = query if line is None else f"[Context: {line}]\n\n{query}"
    messages.append(HumanMessage(content=final))
    return messages
