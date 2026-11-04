# Prove your tests: PASS

- test command: `python3 -m unittest -q tests.test_guard_effect`
- repo head: 86c9824211d40dd25a3d60a505e1a164cd6f1631
- plants file sha256: a954f7ed203b, shard all
- baseline: PASSED
- plants: 25 planned, 25 killed, 0 survived, 0 not run
- catalog (behavior): 9/9 forms covered
- plant authors: plant.py

## Every plant

| id | form | status | restored | control | seconds | what |
| --- | --- | --- | --- | --- | --- | --- |
| M0001 | M4 | KILLED | True | GREEN | 0.07 | constant at shop.py:10: '50' -> '51' |
| M0002 | M4 | KILLED | True | GREEN | 0.09 | constant at shop.py:17: 'False' -> 'True' |
| M0003 | M4 | KILLED | True | GREEN | 0.09 | constant at shop.py:24: '0' -> '1' |
| M0004 | M7 | KILLED | True | GREEN | 0.06 | negate-if at shop.py:30: 'amount <= 0' -> 'not (amount <= 0)' |
| M0005 | M1 | KILLED | True | GREEN | 0.07 | compare at shop.py:30: '<=' -> '<' |
| M0006 | M4 | KILLED | True | GREEN | 0.06 | constant at shop.py:30: '0' -> '1' |
| M0007 | M7 | KILLED | True | GREEN | 0.09 | negate-if at shop.py:32: 'amount > order.paid - order.refunded' -> 'not (amount > order.paid - order.refunded)' |
| M0008 | M1 | KILLED | True | GREEN | 0.09 | compare at shop.py:32: '>' -> '>=' |
| M0009 | M2 | KILLED | True | GREEN | 0.1 | arith at shop.py:32: '-' -> '+' |
| M0010 | M5 | KILLED | True | GREEN | 0.07 | drop-not at shop.py:34: 'not user.is_admin' -> '(user.is_admin)' |
| M0011 | M7 | KILLED | True | GREEN | 0.11 | negate-if at shop.py:34: 'not user.is_admin and amount > MAX_SELF_REFUND' -> 'not (not user.is_admin and amount > MAX_SE |
| M0012 | M3 | KILLED | True | GREEN | 0.06 | bool at shop.py:34: 'and' -> 'or' |
| M0013 | M1 | KILLED | True | GREEN | 0.05 | compare at shop.py:34: '>' -> '>=' |
| M0014 | M8 | KILLED | True | GREEN | 0.07 | drop-call at shop.py:37: 'LEDGER.append({"order": order.id, "amount": -amount, "by": user.name})' -> 'pass' |
| M0015 | M6 | KILLED | True | GREEN | 0.06 | return-none at shop.py:38: 'order.refunded' -> 'None' |
| M0016 | M8 | KILLED | True | GREEN | 0.06 | drop-call at shop.py:43: 'order.notes.append((user.name, text.strip()))' -> 'pass' |
| M0017 | M6 | KILLED | True | GREEN | 0.06 | return-none at shop.py:44: 'len(order.notes)' -> 'None' |
| M0018 | M6 | KILLED | True | GREEN | 0.06 | return-none at shop.py:49: 'order.paid - order.refunded' -> 'None' |
| M0019 | M2 | KILLED | True | GREEN | 0.06 | arith at shop.py:49: '-' -> '+' |
| M0020 | M7 | KILLED | True | GREEN | 0.06 | negate-if at shop.py:55: 'left == 0' -> 'not (left == 0)' |
| M0021 | M1 | KILLED | True | GREEN | 0.05 | compare at shop.py:55: '==' -> '!=' |
| M0022 | M4 | KILLED | True | GREEN | 0.05 | constant at shop.py:55: '0' -> '1' |
| M0023 | M4 | KILLED | True | GREEN | 0.05 | constant at shop.py:56: '0' -> '1' |
| M0024 | M6 | KILLED | True | GREEN | 0.06 | return-none at shop.py:56: '0' -> 'None' |
| M0025 | M6 | KILLED | True | GREEN | 0.06 | return-none at shop.py:57: 'refund(order, left, user)' -> 'None' |
