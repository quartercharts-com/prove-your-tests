# Plant catalog

Two families. A run covers EVERY form of its family: at least one plant per form that can exist in the
code, or one `n/a` line saying why it cannot (`{"form": "E12", "na": "no HTTP routes in this code"}`).
`prove.py` will not say PASS while a form has neither.

Add a form the day someone finds a bug class this list missed. Never remove one.

## Behavior plants (mode `behavior`): change a line, a test must notice

`plant.py` writes these by itself for Python and JS/TS. Write them by hand for other languages.

| id | form | example |
| --- | --- | --- |
| M1 | comparison flipped or moved by one | `age >= 18` to `age > 18`; `==` to `!=` |
| M2 | arithmetic swapped | `paid - refunded` to `paid + refunded` |
| M3 | `and` / `or` swapped | `a and b` to `a or b` |
| M4 | constant changed | `50` to `51`; `True` to `False` |
| M5 | `not` dropped | `if not user.is_admin` to `if (user.is_admin)` |
| M6 | return value replaced | `return total` to `return None` |
| M7 | `if` condition negated | `if x:` to `if not (x):` |
| M8 | call dropped | `audit.log(...)` to `pass` |
| M9 | error swallowed or re-raised | `except E: fallback()` to `except E: raise` |

## Escape plants (mode `guard`): add code that reaches the forbidden effect, a guard must notice

A guard is a test that protects a rule such as "only `refund()` moves money", "no route answers without
sign-in", "nothing writes the `accounts` table except sign-up". Escape plants keep the code running and
reach the forbidden effect in a form the guard's author may not have thought of. A separate plant writer
writes them (see `agents/plant-writer.md`), after `scan_forms.py` lists the repo's real call forms.

| id | form | example |
| --- | --- | --- |
| E1 | alias import | `from billing import charge as c; c(...)` |
| E2 | module attribute | `import billing as b; b.charge(...)` |
| E3 | getattr or string dispatch | `getattr(svc, "charge")(...)`; `HANDLERS["charge"](...)` |
| E4 | keyword, `**kwargs` or default argument | the dangerous value by keyword, by `**opts`, or left to a default |
| E5 | stored callable | kept in a dict, list, class attribute, `lambda` or `functools.partial`, called later |
| E6 | subclass, override or wrapper | a subclass overrides the guarded method; a decorator wraps it |
| E7 | raw transport | the same effect by raw HTTP (`requests`, `httpx`, `fetch`), raw SQL or a shell call |
| E8 | async or thread twin | an `async def` copy, `asyncio.to_thread`, a background task, a queue consumer |
| E9 | second writer or reader | another module, job, CLI or migration that reaches the same table, file or endpoint |
| E10 | house constants | the value built from the repo's own constants, enums or settings, not a literal |
| E11 | spelling and type variants | case, accents, synonyms, padded or unicode digits, a number for a string, bool, None, empty, very long |
| E12 | every method and route form | GET, POST, PUT, PATCH, DELETE, HEAD; trailing slash; versioned and unversioned path |
| E13 | false backstop | a comment, docstring or log line that claims a check the code does not do |
| E14 | error path | the effect reached inside an `except`, a retry, a fallback or a timeout branch |
| E15 | config switch | the effect reached with a flag, env var or plan setting flipped (every spelling) |

## How to plant well

1. **Scan first.** `scan_forms.py --repo . --name <guarded name>` lists the forms the repo already uses.
   Plant one copy of each real form before inventing new ones.
2. **Never read the tests or the guard.** The plant writer sees the code under test, the scan and this
   catalog. Plants written by the guard's author share its blind spots (measured on real pull requests: an
   author's own guard caught 3 of 19 independent plants, then 19 of 19 after it was fixed).
3. **Prefer effect checks for money, accounts and access.** "No charge row, no account row, no write, no
   2xx" catches forms nobody listed; a name or text pattern catches only the names it lists.
4. **Write the business numbers into the test.** A test that reads the code's own constant moves with it:
   it cannot notice `MAX_REFUND = 50` becoming `51`.
5. **Red and green, every plant.** `prove.py` runs the tests with the plant (must be RED), restores the file
   byte-identical, and runs them again (must be GREEN). A plant that only "passes" one side proves nothing.
