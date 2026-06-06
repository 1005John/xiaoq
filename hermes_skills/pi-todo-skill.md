---
name: pi-todo
description: "manage todos. use when user wants to add, list, complete, or delete todos."
---

# Todo Management

## CRITICAL: Response Format

EVERY reply MUST end with exactly ONE line of JSON for backend execution:

```
{"action":"add","text":"user's full input"}
{"action":"done","index":1}
{"action":"delete","index":2}
{"action":"query"}
```

This JSON line is stripped before showing to user - it is ONLY for backend automation. You MUST include it.

## Query todos
Run: python3 ~/.hermes/skills/pi-todo/query.py
End reply with: {"action":"query"}

## Add todo
Pass user's exact words in text field. End reply with: {"action":"add","text":"user's full request"}

## Complete todo N
End reply with: {"action":"done","index":N}

## Delete todo N
End reply with: {"action":"delete","index":N}
