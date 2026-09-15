import importlib
import gc
import os
import tempfile
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


class PaymentHandoffTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        handle.close()
        self.database_path = handle.name
        self.original_database_path = bot.DATABASE_PATH
        self.original_review_chat_id = bot.ADMIN_REVIEW_CHAT_ID
        self.original_topic_id = bot.PAYMENT_FULFILMENT_TOPIC_ID
        bot.DATABASE_PATH = self.database_path
        bot.ADMIN_REVIEW_CHAT_ID = -1004438876540
        bot.PAYMENT_FULFILMENT_TOPIC_ID = 77
        bot.init_db()

    def tearDown(self):
        bot.DATABASE_PATH = self.original_database_path
        bot.ADMIN_REVIEW_CHAT_ID = self.original_review_chat_id
        bot.PAYMENT_FULFILMENT_TOPIC_ID = self.original_topic_id
        gc.collect()
        os.unlink(self.database_path)

    async def test_only_approved_payment_is_handed_off_once(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 verified_at, screenshot_file_id, reviewed_by, reviewed_by_name,
                 fulfilment_status)
                VALUES ('pay-1', 42, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', 7, 'Megha', 'pending')"""
            )
        sent = SimpleNamespace(message_id=123)
        with patch.object(bot.bot, "send_photo", AsyncMock(return_value=sent)) as send_photo:
            self.assertTrue(await bot.deliver_payment_handoff("pay-1"))
            self.assertTrue(await bot.deliver_payment_handoff("pay-1"))

        send_photo.assert_awaited_once()
        self.assertEqual(send_photo.await_args.kwargs["message_thread_id"], 77)
        self.assertIn("Buyer/User ID", send_photo.await_args.kwargs["caption"])
        with bot.db_connect() as connection:
            row = connection.execute(
                "SELECT fulfilment_status, fulfilment_message_id FROM upi_payments WHERE payment_id='pay-1'"
            ).fetchone()
        self.assertEqual(row["fulfilment_status"], "sent")
        self.assertEqual(row["fulfilment_message_id"], 123)

    async def test_pending_payment_is_never_handed_off(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 screenshot_file_id, fulfilment_status)
                VALUES ('pay-2', 42, 'chat', 999, 'pending', 'now',
                        'photo-file', 'not_ready')"""
            )
        with patch.object(bot.bot, "send_photo", AsyncMock()) as send_photo:
            self.assertFalse(await bot.deliver_payment_handoff("pay-2"))
        send_photo.assert_not_awaited()

    async def test_handoff_uses_actual_approver_name(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 verified_at, screenshot_file_id, reviewed_by, reviewed_by_name,
                 fulfilment_status)
                VALUES ('pay-3', 42, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', 1001, '@ash_ops', 'pending')"""
            )
        sent = SimpleNamespace(message_id=124)
        with patch.object(bot.bot, "send_photo", AsyncMock(return_value=sent)) as send_photo:
            self.assertTrue(await bot.deliver_payment_handoff("pay-3"))

        caption = send_photo.await_args.kwargs["caption"]
        self.assertIn("Approved by: @ash_ops", caption)
        self.assertNotIn("Only payments explicitly approved by Megha", caption)

if __name__ == "__main__":
    unittest.main()
