# Prove your tests: FAIL

- test command: `python3 -m unittest -q tests.test_shop_weak`
- repo head: 86c9824211d40dd25a3d60a505e1a164cd6f1631
- plants file sha256: a954f7ed203b, shard all
- baseline: PASSED
- plants: 25 planned, 10 killed, 15 survived, 0 not run
- catalog (behavior): 9/9 forms covered
- plant authors: plant.py

## Why not PASS

- M0001 SURVIVED (M4): constant at shop.py:10: '50' -> '51'
- M0002 SURVIVED (M4): constant at shop.py:17: 'False' -> 'True'
- M0005 SURVIVED (M1): compare at shop.py:30: '<=' -> '<'
- M0006 SURVIVED (M4): constant at shop.py:30: '0' -> '1'
- M0008 SURVIVED (M1): compare at shop.py:32: '>' -> '>='
- M0009 SURVIVED (M2): arith at shop.py:32: '-' -> '+'
- M0013 SURVIVED (M1): compare at shop.py:34: '>' -> '>='
- M0018 SURVIVED (M6): return-none at shop.py:49: 'order.paid - order.refunded' -> 'None'
- M0019 SURVIVED (M2): arith at shop.py:49: '-' -> '+'
- M0020 SURVIVED (M7): negate-if at shop.py:55: 'left == 0' -> 'not (left == 0)'
- M0021 SURVIVED (M1): compare at shop.py:55: '==' -> '!='
- M0022 SURVIVED (M4): constant at shop.py:55: '0' -> '1'
- M0023 SURVIVED (M4): constant at shop.py:56: '0' -> '1'
- M0024 SURVIVED (M6): return-none at shop.py:56: '0' -> 'None'
- M0025 SURVIVED (M6): return-none at shop.py:57: 'refund(order, left, user)' -> 'None'

## Every plant

| id | form | status | restored | control | seconds | what |
| --- | --- | --- | --- | --- | --- | --- |
| M0001 | M4 | SURVIVED | True |  | 0.08 | constant at shop.py:10: '50' -> '51' |
| M0002 | M4 | SURVIVED | True |  | 0.08 | constant at shop.py:17: 'False' -> 'True' |
| M0003 | M4 | KILLED | True | GREEN | 0.06 | constant at shop.py:24: '0' -> '1' |
| M0004 | M7 | KILLED | True | GREEN | 0.05 | negate-if at shop.py:30: 'amount <= 0' -> 'not (amount <= 0)' |
| M0005 | M1 | SURVIVED | True |  | 0.06 | compare at shop.py:30: '<=' -> '<' |
| M0006 | M4 | SURVIVED | True |  | 0.06 | constant at shop.py:30: '0' -> '1' |
| M0007 | M7 | KILLED | True | GREEN | 0.07 | negate-if at shop.py:32: 'amount > order.paid - order.refunded' -> 'not (amount > order.paid - order.refunded)' |
| M0008 | M1 | SURVIVED | True |  | 0.07 | compare at shop.py:32: '>' -> '>=' |
| M0009 | M2 | SURVIVED | True |  | 0.06 | arith at shop.py:32: '-' -> '+' |
| M0010 | M5 | KILLED | True | GREEN | 0.07 | drop-not at shop.py:34: 'not user.is_admin' -> '(user.is_admin)' |
| M0011 | M7 | KILLED | True | GREEN | 0.07 | negate-if at shop.py:34: 'not user.is_admin and amount > MAX_SELF_REFUND' -> 'not (not user.is_admin and amount > MAX_SE |
| M0012 | M3 | KILLED | True | GREEN | 0.07 | bool at shop.py:34: 'and' -> 'or' |
| M0013 | M1 | SURVIVED | True |  | 0.08 | compare at shop.py:34: '>' -> '>=' |
| M0014 | M8 | KILLED | True | GREEN | 0.07 | drop-call at shop.py:37: 'LEDGER.append({"order": order.id, "amount": -amount, "by": user.name})' -> 'pass' |
| M0015 | M6 | KILLED | True | GREEN | 0.06 | return-none at shop.py:38: 'order.refunded' -> 'None' |
| M0016 | M8 | KILLED | True | GREEN | 0.06 | drop-call at shop.py:43: 'order.notes.append((user.name, text.strip()))' -> 'pass' |
| M0017 | M6 | KILLED | True | GREEN | 0.08 | return-none at shop.py:44: 'len(order.notes)' -> 'None' |
| M0018 | M6 | SURVIVED | True |  | 0.08 | return-none at shop.py:49: 'order.paid - order.refunded' -> 'None' |
| M0019 | M2 | SURVIVED | True |  | 0.06 | arith at shop.py:49: '-' -> '+' |
| M0020 | M7 | SURVIVED | True |  | 0.07 | negate-if at shop.py:55: 'left == 0' -> 'not (left == 0)' |
| M0021 | M1 | SURVIVED | True |  | 0.06 | compare at shop.py:55: '==' -> '!=' |
| M0022 | M4 | SURVIVED | True |  | 0.09 | constant at shop.py:55: '0' -> '1' |
| M0023 | M4 | SURVIVED | True |  | 0.15 | constant at shop.py:56: '0' -> '1' |
| M0024 | M6 | SURVIVED | True |  | 0.08 | return-none at shop.py:56: '0' -> 'None' |
| M0025 | M6 | SURVIVED | True |  | 0.08 | return-none at shop.py:57: 'refund(order, left, user)' -> 'None' |
