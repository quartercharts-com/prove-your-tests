"""The tests a busy team writes first: they pass, and they look fine."""
import unittest

import shop


class ShopTests(unittest.TestCase):
    def setUp(self):
        shop.LEDGER.clear()

    def test_customer_small_refund(self):
        order = shop.Order("A1", paid=100)
        self.assertEqual(shop.refund(order, 10, shop.User("ana")), 10)

    def test_admin_big_refund(self):
        order = shop.Order("A2", paid=300)
        shop.refund(order, 200, shop.User("boss", is_admin=True))
        self.assertEqual(len(shop.LEDGER), 1)

    def test_note(self):
        order = shop.Order("A3", paid=10)
        self.assertEqual(shop.add_note(order, "hi", shop.User("ana")), 1)


if __name__ == "__main__":
    unittest.main()
