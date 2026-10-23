
import re
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

agent = Agent()
protocol = Protocol(spec=chat_protocol_spec)

HIGH_PRIORITY_KEYWORDS = {
    "fire", "smoke", "gas", "leak", "leaking", "flood", "flooded",
    "spark", "sparking", "electrical", "shock", "hazard", "emergency",
    "trapped", "danger", "collapse", "outage",
}
MEDIUM_PRIORITY_KEYWORDS = {
    "broken", "cracked", "damaged", "clogged", "toilet", "light",
    "lights", "heating", "ac", "window", "door", "lock", "wifi",
    "projector", "dark", "hot", "cold", "noisy", "dirty",
}

HELP_TEXT = (
    "CampusFix AI - campus maintenance tickets\n\n"
    "- Describe a campus problem to open a ticket.\n"
    "- list - show all tickets\n"
    "- status CF-1 - details for a ticket\n"
    "- close CF-1 - resolve a ticket\n"
    "- help - show commands"
)


def normalize(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    ignored = {"the", "a", "an", "is", "are", "in", "on", "at",
               "to", "of", "and", "for", "near", "please", "there"}
    return words - ignored


def find_duplicate(description: str, tickets: dict):
    new_words = normalize(description)
    if not new_words:
        return None

    for ticket in tickets.values():
        if ticket.get("status") != "OPEN":
            continue

        old_words = normalize(ticket.get("description", ""))
        if not old_words:
            continue

        # Jaccard similarity: overlap divided by combined unique words.
        similarity = len(new_words & old_words) / len(new_words | old_words)

        # Also catch short reports with the same core keywords.
        shared = new_words & old_words
        if similarity >= 0.60 or (
            len(shared) >= 2
            and len(shared) / min(len(new_words), len(old_words)) >= 0.80
        ):
            return ticket

    return None


def assign_priority(text: str) -> str:
    words = normalize(text)
    if words & HIGH_PRIORITY_KEYWORDS:
        return "HIGH"
    if words & MEDIUM_PRIORITY_KEYWORDS:
        return "MEDIUM"
    return "LOW"


def parse_command(text: str):
    lower = text.strip().lower()

    if lower in {"help", "menu", "commands"}:
        return "help", None
    if lower in {"list", "tickets", "list tickets"}:
        return "list", None

    for prefix in ("status", "close", "resolve"):
        if lower.startswith(prefix + " "):
            arg = text.strip()[len(prefix):].strip().upper()
            if re.fullmatch(r"CF-\d+", arg):
                return ("close" if prefix == "resolve" else prefix), arg

    return "complaint", text.strip()


@agent.on_event("startup")
async def on_start(ctx: Context):
    ctx.logger.info("CampusFix AI ready.")


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    now = datetime.now(timezone.utc)

    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=now,
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    text = msg.text()
    if not text or not text.strip():
        return

    tickets = ctx.storage.get("tickets") or {}
    action, arg = parse_command(text)

    if action == "help":
        reply = HELP_TEXT

    elif action == "list":
        if not tickets:
            reply = "No tickets yet. Describe a campus problem to open one."
        else:
            ordered = sorted(
                tickets.values(),
                key=lambda t: int(t["id"].split("-")[1]),
            )
            lines = [
                f"{t['id']} | {t['priority']} | {t['status']} | "
                f"{t['description'][:60]}"
                for t in ordered
            ]
            reply = "All tickets:\n" + "\n".join(lines)

    elif action in {"status", "close"}:
        ticket = tickets.get(arg)

        if ticket is None:
            reply = f"No ticket found with ID {arg}. Use 'list' to see tickets."
        elif action == "status":
            reply = (
                f"Ticket {ticket['id']}\n"
                f"Status: {ticket['status']}\n"
                f"Priority: {ticket['priority']}\n"
                f"Reported: {ticket['created']}\n"
                f"Description: {ticket['description']}"
            )
        else:
            ticket["status"] = "RESOLVED"
            tickets[ticket["id"]] = ticket
            ctx.storage.set("tickets", tickets)
            reply = f"Ticket {ticket['id']} marked RESOLVED."

    else:
        duplicate = find_duplicate(arg, tickets)

        if duplicate:
            reply = (
                f"Possible duplicate detected. I did not create another ticket.\n"
                f"Existing ticket: {duplicate['id']}\n"
                f"Priority: {duplicate['priority']}\n"
                f"Status: {duplicate['status']}\n"
                f"Description: {duplicate['description']}\n"
                f"Check it with 'status {duplicate['id']}'."
            )
        else:
            next_id = ctx.storage.get("next_id") or 1
            ticket_id = f"CF-{next_id}"
            priority = assign_priority(arg)

            tickets[ticket_id] = {
                "id": ticket_id,
                "description": arg,
                "priority": priority,
                "status": "OPEN",
                "created": now.isoformat(timespec="seconds"),
                "reporter": sender,
            }

            ctx.storage.set("tickets", tickets)
            ctx.storage.set("next_id", next_id + 1)

            ctx.logger.info(f"Created {ticket_id} ({priority})")
            reply = (
                f"Ticket {ticket_id} created (priority: {priority}).\n"
                f"Description: {arg}\n"
                f"Track it with 'status {ticket_id}' or "
                f"resolve it with 'close {ticket_id}'."
            )

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=reply)],
        ),
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()

