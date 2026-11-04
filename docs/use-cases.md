# Where prove-your-tests helps

These are illustrations of the kind of bug the tool exposes, written for this page. They are not results from
any client or project, and nothing here is a measured claim except the shop example in `examples/shop/`.

## Payments and fintech
A refund limit is checked with `amount > limit`, but `amount` arrives as text from a form, so `"100" > "50"` is
false and a refund of 100 passes. A test that only tries 51 stays green. An M1 or M4 plant around the comparison,
or a guard test that tries 51, 99, 100 and 1000, turns it red. The shop example in this repo shows exactly this.
Two more: a blank amount silently treated as 0 (an M4 plant that changes a default), and a refund that can run
twice (an escape plant that calls the refund through a second path, form E9).

## E-commerce
A 10% discount starts at 100: `total >= 100`. A plant that changes it to `total > 100` survives when no test
uses exactly 100. A coupon applied after tax instead of before survives when the tests only check that "some
discount" was applied (M2 plants that swap the order of operations).

## SaaS access and accounts
Only `require_admin()` may grant a role. A guard test that greps for `grant_role(` misses
`from roles import grant_role as g` (E1 alias), `getattr(roles, "grant_role")` (E3) and a second module that
writes the roles table directly (E9). An effect test (log in as a normal user, call every route, then check that
no role changed) catches all three. Same shape: a sign-up that skips email verification when the request is
retried (an escape plant on the retry path).

## Dosage-style calculators
`dose_mg = weight_kg * 10`, tested with one weight. Plants that turn `10` into `100` (mg vs g) or move an age
boundary from `>= 18` to `> 18` survive when the tests never touch the boundary or the unit.

## Data pipelines and analytics
A loader writes `value or 0`, so a missing value becomes a real-looking 0 (M4 plant on the default). A batch
that times out drops its last row (M8 dropped call on the flush). A second writer that skips validation (E9).
A test that counts rows in equals rows out, and that a blank stays blank, turns each red.

## Code written by an AI
When the same model writes the code and the tests, the tests tend to share the code's blind spots. Plants
written by a different model, which never reads the tests, are a cheap way to find those shared gaps.

## Regulated teams (audits, SOX, PCI DSS, ISO 27001 style controls)
A coverage percent shows that lines ran, not that a test would fail on a defect. A prove-your-tests report (every
plant, killed or not, files restored byte-identical) can support the evidence that key controls are tested. It
does not make anyone compliant.

## Open source maintainers
For a contributor pull request: `prove-your-tests plant --lines src/x.py:120-160 ...` plants only on the changed
lines, then `prove-your-tests prove` shows whether the new tests would catch a regression there.
