import importlib
import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("PAYMENT_CHANNEL_ID", "123456")

bot = importlib.import_module("bot")


class MenuPayloadTests(unittest.TestCase):
    def test_only_new_services_are_available(self):
        self.assertEqual(set(bot.PRODUCTS), {"chat", "video"})
        self.assertEqual(bot.get_product_name("chat"), "Chat with Me")
        self.assertEqual(bot.get_product_name("video"), "Private Video Call")

    def test_fixed_star_and_upi_prices(self):
        self.assertEqual(bot.PRODUCTS["chat"]["amount"], 999)
        self.assertEqual(bot.PRODUCTS["chat"]["upi_amount"], 1998)
        self.assertEqual(bot.PRODUCTS["video"]["amount"], 4999)
        self.assertEqual(bot.PRODUCTS["video"]["upi_amount"], 9998)

    def test_subscription_period_is_thirty_days(self):
        self.assertEqual(bot.SUBSCRIPTION_PERIOD, 30 * 24 * 60 * 60)


if __name__ == "__main__":
    unittest.main()
