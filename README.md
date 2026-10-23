# CampusFix AI

## Overview
CampusFix AI is a lightweight maintenance assistant for campuses. Students and staff describe a problem in chat, and the agent opens a numbered maintenance ticket with an automatically assigned priority. Tickets are stored persistently so they can be reviewed, tracked, and closed later.

## Features
- Opens a numbered ticket (CF-1, CF-2, ...) for any reported campus problem
- Rule-based priority assignment: HIGH for hazards like leaks, fire, or electrical issues; MEDIUM for broken fixtures like lights, doors, or heating; LOW otherwise
- Ticket tracking commands: list all tickets, view one ticket's details, close a resolved ticket
- Persistent ticket storage via agent storage, so tickets survive restarts
- Simple chat interface built on the Agent Chat Protocol with acknowledgements

## Limitations
- Priority assignment uses keyword rules, not an LLM
- Tickets are shared across all chats with this agent; no per-user access control

## Duplicate Detection

Before creating a ticket, check all existing tickets in persistent storage.

- Compare the issue category, location, description, and status.
- If an unresolved ticket already reports the same problem at the same location, return its existing ticket ID.
- Do not create a second ticket for the same unresolved incident.
- Create a new ticket only when no matching unresolved ticket exists.
- If the ticket storage tool fails, report the error instead of claiming the check succeeded.

## Required Ticket Workflow

1. Check existing tickets.
2. Detect duplicates.
3. If a duplicate exists, return its ticket ID.
4. Otherwise, assign priority and create a new ticket.
5. Confirm the result only after the database operation succeeds.