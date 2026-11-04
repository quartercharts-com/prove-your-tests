"""An effect guard: drive every public function as a customer and look at the money itself.

It does not care HOW the code reaches the ledger (alias, getattr, a stored
callable, a second list): it checks what happened to the money.
"""
import copy
import inspect
import unittest

import shop

CUSTOMER = shop.User("ana")
ADMIN = shop.User("boss", is_admin=True)


def money_out(before, after):
    return -sum(e["amount"] for e in after[len(before):])


class EffectGuard(unittest.TestCase):
    def setUp(self):
        shop.LEDGER.clear()

    def snapshot(self):
        return copy.deepcopy(shop.LEDGER)

    def test_non_refund_functions_move_no_money(self):
        for name, fn in inspect.getmembers(shop, inspect.isfunction):
            if fn.__module__ != "shop" or name in {"refund", "cancel"}:
                continue
            order = shop.Order("G1", paid=500)
            before, paid_before = self.snapshot(), (order.paid, order.refunded)
            args = {"order": order, "user": CUSTOMER, "text": "note", "amount": 1}
            fn(**{k: args[k] for k in inspect.signature(fn).parameters if k in args})
            self.assertEqual(shop.LEDGER, before, f"{name} changed the ledger")
            self.assertEqual((order.paid, order.refunded), paid_before, f"{name} changed the order's money")

    def test_customer_limit_holds_at_and_past_the_line(self):
        # the business number is written here, not read from shop: a test that reads the
        # code's own constant moves with it and can never catch a changed limit
        order = shop.Order("G2", paid=500)
        before = self.snapshot()
        self.assertEqual(shop.refund(order, 50, CUSTOMER), 50)
        self.assertEqual(money_out(before, shop.LEDGER), 50)
        with self.assertRaises(PermissionError):
            shop.refund(order, 51, CUSTOMER)
        self.assertEqual(money_out(before, shop.LEDGER), 50)
        self.assertEqual(order.refunded, 50)

    def test_customer_limit_holds_far_past_the_line(self):
        # 51 alone is not enough: compared as text, "100" < "50", so try several sizes
        for amount in (51, 99, 100, 499, 1000):
            order = shop.Order(f"G2-{amount}", paid=5000)
            with self.assertRaises(PermissionError, msg=f"customer refund of {amount}"):
                shop.refund(order, amount, CUSTOMER)
            self.assertEqual(order.refunded, 0)
        self.assertEqual(shop.LEDGER, [])

    def test_never_more_than_paid_and_never_zero(self):
        order = shop.Order("G3", paid=30)
        for bad in (0, -5, 31):
            with self.assertRaises(ValueError):
                shop.refund(order, bad, ADMIN)
        self.assertEqual(shop.LEDGER, [])
        self.assertEqual(shop.refund(order, 1, ADMIN), 1)  # the smallest legal refund
        self.assertEqual(shop.refund(order, 29, ADMIN), 30)
        self.assertEqual(shop.LEDGER, [{"order": "G3", "amount": -1, "by": "boss"},
                                       {"order": "G3", "amount": -29, "by": "boss"}])
        with self.assertRaises(ValueError):
            shop.refund(order, 1, ADMIN)

    def test_cancel_obeys_the_customer_limit(self):
        order = shop.Order("G4", paid=80)
        with self.assertRaises(PermissionError):
            shop.cancel(order, CUSTOMER)
        self.assertEqual(shop.LEDGER, [])
        self.assertEqual(shop.cancel(order, ADMIN), 80)
        self.assertEqual(shop.order_balance(order), 0)
        self.assertEqual(shop.cancel(order, ADMIN), 0)
        self.assertEqual(len(shop.LEDGER), 1)

    def test_notes_are_kept_and_trimmed(self):
        order = shop.Order("G5", paid=10)
        self.assertEqual(shop.add_note(order, "  hello ", CUSTOMER), 1)
        self.assertEqual(order.notes, [("ana", "hello")])


if __name__ == "__main__":
    unittest.main()
