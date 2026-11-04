# Prove your tests: FAIL

- test command: `python3 -m unittest -q tests.test_guard_pattern`
- repo head: 86c9824211d40dd25a3d60a505e1a164cd6f1631
- plants file sha256: 74869e03489f, shard all
- baseline: PASSED
- plants: 46 planned, 8 killed, 38 survived, 0 not run
- catalog (guard): 15/15 forms covered
- plant authors: plant-writer 2026-11-04 (tests not read)

## Why not PASS

- E0001 SURVIVED (E1): customer cancel of an 80 balance writes an 80 ledger row through an alias-imported helper module, no 50 limit
- E0002 SURVIVED (E1): customer add_note writes a ledger credit row through a module-level alias import
- E0004 SURVIVED (E2): customer cancel of an 80 balance writes an 80 ledger row via module.refund with a module.User admin
- E0005 SURVIVED (E3): customer add_note writes a ledger row via getattr(LEDGER, 'append')
- E0006 SURVIVED (E3): customer add_note refunds the whole open balance via globals()['ref'+'und'] with an admin user
- E0007 SURVIVED (E3): customer cancel of an 80 balance writes an 80 ledger row via getattr(LEDGER, 'ext'+'end')
- E0008 SURVIVED (E4): customer refund of 80 succeeds: the limit only applies when a 'limit' argument is passed (default None)
- E0009 SURVIVED (E4): customer refund of 80 succeeds: the limit check sits behind a keyword-only flag defaulting to False
- E0010 SURVIVED (E4): customer refund up to the full paid amount succeeds: the cap comes from **opts with order.paid as default
- E0011 SURVIVED (E4): customer cancel of an 80 balance writes an 80 ledger row: cancel passes user by **dict with is_admin=True
- E0012 SURVIVED (E5): customer add_note writes a ledger row through a stored bound method _POST = LEDGER.append
- E0013 SURVIVED (E5): order_balance (a read) writes a ledger row through a lambda kept in a hooks list
- E0014 SURVIVED (E5): customer cancel of an 80 balance writes an 80 ledger row through functools.partial(refund, user=admin)
- E0015 SURVIVED (E5): customer add_note writes a ledger row through a class attribute holding LEDGER.append
- E0016 SURVIVED (E6): customer refund of 80 succeeds: a decorator on refund() swaps the caller for an admin User
- E0017 SURVIVED (E6): customer refund of 80 succeeds: a User.__post_init__ override makes every named user an admin
- E0018 SURVIVED (E6): customer refund of 80 in ONE call succeeds: a wrapper redefines refund() to split it into 50-chunks (two ledger rows)
- E0019 SURVIVED (E7): customer add_note writes a ledger row through the unbound list.append(LEDGER, row)
- E0020 SURVIVED (E7): customer cancel of an 80 balance writes an 80 ledger row by raw slice assignment LEDGER[len:] = [row]
- E0021 SURVIVED (E7): customer add_note writes a ledger row built by a shell subprocess and stored with LEDGER.__iadd__
- E0023 SURVIVED (E8): customer cancel of an 80 balance writes an 80 ledger row through an async copy of refund() without the limit
- E0024 SURVIVED (E8): customer add_note refunds up to 50 via a thread-pool worker running refund() as admin
- E0027 SURVIVED (E9): customer cancel of an 80 balance writes an 80 ledger row from a separate 'nightly job' module
- E0028 SURVIVED (E10): customer refund of 80 succeeds: the cap is MAX_SELF_REFUND * 2
- E0029 SURVIVED (E10): customer refund of 80 succeeds: the cap is a derived MAX_SELF_REFUND_CENTS (5000)
- E0030 SURVIVED (E10): refund of 30 on an order that paid 10 succeeds: the paid check gets MAX_SELF_REFUND of slack
- E0031 SURVIVED (E11): refund of -10 writes a +10 ledger row: the positive check is falsy-only (if not amount)
- E0032 SURVIVED (E11): customer refund of 100 succeeds: the cap compares numbers as strings ('100' < '50')
- E0033 SURVIVED (E11): customer refund of 80 (anything up to 99) succeeds: the cap compares digit counts
- E0036 SURVIVED (E13): customer refund of 80 succeeds: the limit check is replaced by a comment claiming cancel()/the UI enforce it
- E0037 SURVIVED (E13): customer refund of 80 succeeds: over-limit only logs 'refund blocked' and carries on
- E0038 SURVIVED (E13): refund of -10 writes a +10 ledger row: the positive check is replaced by a comment claiming it is guaranteed upstream
- E0040 SURVIVED (E14): customer cancel of an 80 balance writes an 80 ledger row: the PermissionError is retried as an admin
- E0041 SURVIVED (E14): refund of 30 on an order that paid 10 succeeds: the 'more than was paid' ValueError is swallowed
- E0043 SURVIVED (E15): customer refund of 80 succeeds: the limit is enforced only when env SHOP_ENFORCE_REFUND_LIMIT is truthy (unset = off)
- E0044 SURVIVED (E15): customer refund of 80 succeeds: the limit applies only on SETTINGS plan 'free' and the default plan is 'pro'
- E0045 SURVIVED (E15): refund of 30 on an order that paid 10 succeeds: the paid check runs only when SHOP_ENV == 'prod' (default 'dev')
- E0046 SURVIVED (E15): refund of -10 writes a +10 ledger row: the positive check runs only when env SHOP_STRICT is set (unset = off)

## Every plant

| id | form | status | restored | control | seconds | what |
| --- | --- | --- | --- | --- | --- | --- |
| E0001 | E1 | SURVIVED | True |  | 0.06 | customer cancel of an 80 balance writes an 80 ledger row through an alias-imported helper module, no 50 limit |
| E0002 | E1 | SURVIVED | True |  | 0.06 | customer add_note writes a ledger credit row through a module-level alias import |
| E0003 | E2 | KILLED | True | GREEN | 0.07 | customer add_note writes a ledger row through the module object attribute sys.modules[__name__].LEDGER |
| E0004 | E2 | SURVIVED | True |  | 0.06 | customer cancel of an 80 balance writes an 80 ledger row via module.refund with a module.User admin |
| E0005 | E3 | SURVIVED | True |  | 0.06 | customer add_note writes a ledger row via getattr(LEDGER, 'append') |
| E0006 | E3 | SURVIVED | True |  | 0.06 | customer add_note refunds the whole open balance via globals()['ref'+'und'] with an admin user |
| E0007 | E3 | SURVIVED | True |  | 0.07 | customer cancel of an 80 balance writes an 80 ledger row via getattr(LEDGER, 'ext'+'end') |
| E0008 | E4 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the limit only applies when a 'limit' argument is passed (default None) |
| E0009 | E4 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the limit check sits behind a keyword-only flag defaulting to False |
| E0010 | E4 | SURVIVED | True |  | 0.06 | customer refund up to the full paid amount succeeds: the cap comes from **opts with order.paid as default |
| E0011 | E4 | SURVIVED | True |  | 0.06 | customer cancel of an 80 balance writes an 80 ledger row: cancel passes user by **dict with is_admin=True |
| E0012 | E5 | SURVIVED | True |  | 0.05 | customer add_note writes a ledger row through a stored bound method _POST = LEDGER.append |
| E0013 | E5 | SURVIVED | True |  | 0.07 | order_balance (a read) writes a ledger row through a lambda kept in a hooks list |
| E0014 | E5 | SURVIVED | True |  | 0.06 | customer cancel of an 80 balance writes an 80 ledger row through functools.partial(refund, user=admin) |
| E0015 | E5 | SURVIVED | True |  | 0.06 | customer add_note writes a ledger row through a class attribute holding LEDGER.append |
| E0016 | E6 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: a decorator on refund() swaps the caller for an admin User |
| E0017 | E6 | SURVIVED | True |  | 0.07 | customer refund of 80 succeeds: a User.__post_init__ override makes every named user an admin |
| E0018 | E6 | SURVIVED | True |  | 0.06 | customer refund of 80 in ONE call succeeds: a wrapper redefines refund() to split it into 50-chunks (two ledger rows) |
| E0019 | E7 | SURVIVED | True |  | 0.06 | customer add_note writes a ledger row through the unbound list.append(LEDGER, row) |
| E0020 | E7 | SURVIVED | True |  | 0.11 | customer cancel of an 80 balance writes an 80 ledger row by raw slice assignment LEDGER[len:] = [row] |
| E0021 | E7 | SURVIVED | True |  | 0.07 | customer add_note writes a ledger row built by a shell subprocess and stored with LEDGER.__iadd__ |
| E0022 | E8 | KILLED | True | GREEN | 0.06 | customer add_note writes a ledger row from a background thread (Thread(target=LEDGER.append)) |
| E0023 | E8 | SURVIVED | True |  | 0.06 | customer cancel of an 80 balance writes an 80 ledger row through an async copy of refund() without the limit |
| E0024 | E8 | SURVIVED | True |  | 0.07 | customer add_note refunds up to 50 via a thread-pool worker running refund() as admin |
| E0025 | E9 | KILLED | True | GREEN | 0.06 | customer add_note writes a ledger row directly (second writer of LEDGER) |
| E0026 | E9 | KILLED | True | GREEN | 0.06 | order_balance (a read) writes a -1 'rounding credit' ledger row |
| E0027 | E9 | SURVIVED | True |  | 0.07 | customer cancel of an 80 balance writes an 80 ledger row from a separate 'nightly job' module |
| E0028 | E10 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the cap is MAX_SELF_REFUND * 2 |
| E0029 | E10 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the cap is a derived MAX_SELF_REFUND_CENTS (5000) |
| E0030 | E10 | SURVIVED | True |  | 0.06 | refund of 30 on an order that paid 10 succeeds: the paid check gets MAX_SELF_REFUND of slack |
| E0031 | E11 | SURVIVED | True |  | 0.06 | refund of -10 writes a +10 ledger row: the positive check is falsy-only (if not amount) |
| E0032 | E11 | SURVIVED | True |  | 0.06 | customer refund of 100 succeeds: the cap compares numbers as strings ('100' < '50') |
| E0033 | E11 | SURVIVED | True |  | 0.06 | customer refund of 80 (anything up to 99) succeeds: the cap compares digit counts |
| E0034 | E12 | KILLED | True | GREEN | 0.06 | customer cancel of an 80 balance writes an 80 ledger row: cancel dispatches to a legacy 'PUT /refund/' route that skips  |
| E0035 | E12 | KILLED | True | GREEN | 0.06 | customer cancel of an 80 balance writes an 80 ledger row: method 'delete' + trailing-slash path falls to a raw default h |
| E0036 | E13 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the limit check is replaced by a comment claiming cancel()/the UI enforce it |
| E0037 | E13 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: over-limit only logs 'refund blocked' and carries on |
| E0038 | E13 | SURVIVED | True |  | 0.09 | refund of -10 writes a +10 ledger row: the positive check is replaced by a comment claiming it is guaranteed upstream |
| E0039 | E14 | KILLED | True | GREEN | 0.06 | customer cancel of an 80 balance writes an 80 ledger row: the PermissionError fallback writes the ledger directly |
| E0040 | E14 | SURVIVED | True |  | 0.06 | customer cancel of an 80 balance writes an 80 ledger row: the PermissionError is retried as an admin |
| E0041 | E14 | SURVIVED | True |  | 0.06 | refund of 30 on an order that paid 10 succeeds: the 'more than was paid' ValueError is swallowed |
| E0042 | E14 | KILLED | True | GREEN | 0.06 | customer add_note writes a goodwill ledger row in the TimeoutError branch of a support notification |
| E0043 | E15 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the limit is enforced only when env SHOP_ENFORCE_REFUND_LIMIT is truthy (unset = off) |
| E0044 | E15 | SURVIVED | True |  | 0.06 | customer refund of 80 succeeds: the limit applies only on SETTINGS plan 'free' and the default plan is 'pro' |
| E0045 | E15 | SURVIVED | True |  | 0.06 | refund of 30 on an order that paid 10 succeeds: the paid check runs only when SHOP_ENV == 'prod' (default 'dev') |
| E0046 | E15 | SURVIVED | True |  | 0.06 | refund of -10 writes a +10 ledger row: the positive check runs only when env SHOP_STRICT is set (unset = off) |
