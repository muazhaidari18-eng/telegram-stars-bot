import importlib
import os
import unittest

os.environ.setdefault("BOT_TOKEN", "123:ABC")
os.environ.setdefault("PAYMENT_CHANNEL_ID", "123456")

bot = importlib.import_module("bot")


class MenuPayloadTests(unittest.TestCase):
    def test_private_chat_payloads_are_available(self):
        self.assertIsNotNone(bot.get_product_info("text_15"))
        self.assertIsNotNone(bot.get_product_info("text_30"))
        self.assertIsNotNone(bot.get_product_info("text_60"))

    def test_voice_call_payloads_are_available(self):
        self.assertIsNotNone(bot.get_product_info("voice_10"))
        self.assertIsNotNone(bot.get_product_info("voice_20"))
        self.assertIsNotNone(bot.get_product_info("voice_30"))

    def test_video_outfit_payloads_are_available(self):
        self.assertIsNotNone(bot.get_product_info("video_custom_outfit_1_10"))
        self.assertIsNotNone(bot.get_product_info("video_custom_outfit_2_10"))
        self.assertIsNotNone(bot.get_product_info("video_ultimate_outfit_1_15"))
        self.assertIsNotNone(bot.get_product_info("video_ultimate_outfit_2_15"))

    def test_admin_product_names_use_new_menu_labels(self):
        self.assertEqual(bot.get_product_name("text_15"), "Sweet Start (15 Minutes)")
        self.assertEqual(bot.get_product_name("voice_20"), "Late Night Vibes (20 Minutes)")
        self.assertEqual(bot.get_product_name("video_ultimate_outfit_2_15"), "Ultimate VIP Experience (15 Minutes) - Outfit #2")


if __name__ == "__main__":
    unittest.main()
