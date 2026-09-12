import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
        self.assertEqual(bot.PRODUCTS["chat"]["upi_amount"], 999)
        self.assertEqual(bot.PRODUCTS["video"]["amount"], 4999)
        self.assertEqual(bot.PRODUCTS["video"]["upi_amount"], 4999)

    def test_private_chat_menu_explains_access_duration(self):
        self.assertIn("one-time payment", bot.PRIVATE_CHAT_TEXT)
        self.assertIn("full 30 days", bot.PRIVATE_CHAT_TEXT)
        self.assertLess(
            bot.PRIVATE_CHAT_TEXT.index("full 30 days"),
            bot.PRIVATE_CHAT_TEXT.index("Choose your payment method"),
        )

class StarsPaymentFlowTests(unittest.IsolatedAsyncioTestCase):
    def query(self, payload):
        return SimpleNamespace(
            data=payload,
            from_user=SimpleNamespace(id=42),
            answer=AsyncMock(),
        )

    async def test_chat_uses_one_time_invoice(self):
        query = self.query("pay_chat")
        with patch.object(bot.bot, "send_invoice", AsyncMock()) as send_invoice:
            await bot.callback_pay_service(query)

        send_invoice.assert_awaited_once()
        self.assertEqual(send_invoice.await_args.kwargs["chat_id"], 42)
        self.assertEqual(send_invoice.await_args.kwargs["payload"], "chat")
        self.assertEqual(send_invoice.await_args.kwargs["currency"], "XTR")
        self.assertEqual(send_invoice.await_args.kwargs["prices"][0].amount, 999)
        self.assertNotIn("subscription_period", send_invoice.await_args.kwargs)
        self.assertNotIn("provider_token", send_invoice.await_args.kwargs)

    async def test_video_keeps_one_time_invoice(self):
        query = self.query("pay_video")
        with patch.object(bot.bot, "send_invoice", AsyncMock()) as send_invoice:
            await bot.callback_pay_service(query)

        send_invoice.assert_awaited_once()
        self.assertEqual(send_invoice.await_args.kwargs["chat_id"], 42)
        self.assertEqual(send_invoice.await_args.kwargs["currency"], "XTR")
        self.assertEqual(send_invoice.await_args.kwargs["prices"][0].amount, 4999)
        self.assertNotIn("subscription_period", send_invoice.await_args.kwargs)
        self.assertNotIn("provider_token", send_invoice.await_args.kwargs)


if __name__ == "__main__":
    unittest.main()
