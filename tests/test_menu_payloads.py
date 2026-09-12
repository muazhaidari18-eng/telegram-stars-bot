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

    def test_subscription_period_is_thirty_days(self):
        self.assertEqual(bot.SUBSCRIPTION_PERIOD, 30 * 24 * 60 * 60)


class StarsPaymentFlowTests(unittest.IsolatedAsyncioTestCase):
    def query(self, payload):
        return SimpleNamespace(
            data=payload,
            from_user=SimpleNamespace(id=42),
            answer=AsyncMock(),
        )

    async def test_chat_uses_recurring_invoice_link(self):
        query = self.query("pay_chat")
        with patch.object(bot.bot, "create_invoice_link", AsyncMock(return_value="https://t.me/$invoice")) as create_link, \
             patch.object(bot.bot, "send_message", AsyncMock()) as send_message, \
             patch.object(bot.bot, "send_invoice", AsyncMock()) as send_invoice:
            await bot.callback_pay_service(query)

        create_link.assert_awaited_once()
        self.assertEqual(create_link.await_args.kwargs["subscription_period"], bot.SUBSCRIPTION_PERIOD)
        self.assertEqual(create_link.await_args.kwargs["currency"], "XTR")
        self.assertNotIn("provider_token", create_link.await_args.kwargs)
        self.assertEqual(create_link.await_args.kwargs["prices"][0].amount, 999)
        send_message.assert_awaited_once()
        send_invoice.assert_not_awaited()

    async def test_video_keeps_one_time_invoice(self):
        query = self.query("pay_video")
        with patch.object(bot.bot, "create_invoice_link", AsyncMock()) as create_link, \
             patch.object(bot.bot, "send_message", AsyncMock()) as send_message, \
             patch.object(bot.bot, "send_invoice", AsyncMock()) as send_invoice:
            await bot.callback_pay_service(query)

        send_invoice.assert_awaited_once()
        self.assertEqual(send_invoice.await_args.kwargs["chat_id"], 42)
        self.assertEqual(send_invoice.await_args.kwargs["currency"], "XTR")
        self.assertEqual(send_invoice.await_args.kwargs["prices"][0].amount, 4999)
        self.assertNotIn("subscription_period", send_invoice.await_args.kwargs)
        self.assertNotIn("provider_token", send_invoice.await_args.kwargs)
        create_link.assert_not_awaited()
        send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
