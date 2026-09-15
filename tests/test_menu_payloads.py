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

    def test_old_upi_review_caption_can_be_recovered(self):
        parsed = bot.parse_upi_review_caption(
            "💳 UPI PAYMENT VERIFICATION\n\n"
            "👤 User: @buyer\n🆔 User ID: 987654321\n"
            "🛍️ Product: Chat with Me\n💰 Amount: ₹999\n"
            "📦 Payment Method: UPI\n⏱️ Submitted: now\n"
            "🧾 Payment ID: abc123\n\n"
            "Please confirm the screenshot, then approve or reject this payment."
        )

        self.assertEqual(parsed["payment_id"], "abc123")
        self.assertEqual(parsed["user_id"], 987654321)
        self.assertEqual(parsed["product_key"], "chat")
        self.assertEqual(parsed["amount"], 999)
        self.assertEqual(parsed["buyer_username"], "@buyer")

    def test_display_name_prefers_username(self):
        user = SimpleNamespace(id=55, username="ash_ops", full_name="Ash")
        self.assertEqual(bot.display_name(user), "@ash_ops")

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
                 verified_at, screenshot_file_id, buyer_username, buyer_full_name,
                 reviewed_by, reviewed_by_name, fulfilment_status)
                VALUES ('pay-1', 42, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', '@buyer42', 'Buyer 42', 7, 'Megha',
                        'pending')"""
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

    async def test_payment_group_admin_can_review_payment(self):
        member = SimpleNamespace(status="administrator")
        with patch.object(bot.bot, "get_chat_member", AsyncMock(return_value=member)):
            self.assertTrue(await bot.can_review_payment(9090))

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
                 verified_at, screenshot_file_id, buyer_username, buyer_full_name,
                 reviewed_by, reviewed_by_name, fulfilment_status)
                VALUES ('pay-3', 42, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', '@buyer42', 'Buyer 42', 1001, '@ash_ops',
                        'pending')"""
            )
        sent = SimpleNamespace(message_id=124)
        with patch.object(bot.bot, "send_photo", AsyncMock(return_value=sent)) as send_photo:
            self.assertTrue(await bot.deliver_payment_handoff("pay-3"))

        caption = send_photo.await_args.kwargs["caption"]
        self.assertIn("Approved by: @ash_ops", caption)
        self.assertNotIn("Only payments explicitly approved by Megha", caption)

    async def test_handoff_includes_buyer_identity_and_profile_link(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 verified_at, screenshot_file_id, buyer_username, buyer_full_name,
                 reviewed_by, reviewed_by_name, fulfilment_status)
                VALUES ('pay-4', 4242, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', '@buyername', 'Buyer Name', 1001, '@megha',
                        'pending')"""
            )
        sent = SimpleNamespace(message_id=125)
        with patch.object(bot.bot, "send_photo", AsyncMock(return_value=sent)) as send_photo:
            self.assertTrue(await bot.deliver_payment_handoff("pay-4"))

        caption = send_photo.await_args.kwargs["caption"]
        self.assertIn("Buyer: @buyername", caption)
        self.assertIn('tg://user?id=4242', caption)

    async def test_handoff_auto_creates_priya_topic_when_missing(self):
        bot.PAYMENT_FULFILMENT_TOPIC_ID = 0
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 verified_at, screenshot_file_id, buyer_username, buyer_full_name,
                 reviewed_by, reviewed_by_name, fulfilment_status)
                VALUES ('pay-6', 4242, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', '@buyername', 'Buyer Name', 1001, '@megha',
                        'pending')"""
            )
        topic = SimpleNamespace(message_thread_id=88)
        sent = SimpleNamespace(message_id=126)
        with patch.object(bot.bot, "create_forum_topic", AsyncMock(return_value=topic)) as create_topic:
            with patch.object(bot.bot, "send_message", AsyncMock()):
                with patch.object(bot.bot, "send_photo", AsyncMock(return_value=sent)) as send_photo:
                    self.assertTrue(await bot.deliver_payment_handoff("pay-6"))

        create_topic.assert_awaited_once()
        self.assertEqual(send_photo.await_args.kwargs["message_thread_id"], 88)
        self.assertEqual(bot.payment_fulfilment_topic_id(), 88)

    async def test_handoff_falls_back_to_main_group_when_topic_creation_fails(self):
        bot.PAYMENT_FULFILMENT_TOPIC_ID = 0
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 verified_at, screenshot_file_id, buyer_username, buyer_full_name,
                 reviewed_by, reviewed_by_name, fulfilment_status)
                VALUES ('pay-7', 4242, 'chat', 999, 'approved', 'now', 'now',
                        'photo-file', '@buyername', 'Buyer Name', 1001, '@megha',
                        'pending')"""
            )
        sent = SimpleNamespace(message_id=127)
        with patch.object(bot.bot, "create_forum_topic", AsyncMock(side_effect=bot.TelegramBadRequest(method=None, message="no topics"))):
            with patch.object(bot.bot, "send_photo", AsyncMock(return_value=sent)) as send_photo:
                self.assertTrue(await bot.deliver_payment_handoff("pay-7"))

        self.assertNotIn("message_thread_id", send_photo.await_args.kwargs)

    def test_pending_upi_payment_finds_existing_pending_review(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO upi_payments
                (payment_id, user_id, product_key, amount, status, created_at,
                 screenshot_file_id, fulfilment_status)
                VALUES ('pay-5', 42, 'chat', 999, 'pending', 'now',
                        'photo-file', 'not_ready')"""
            )

        self.assertEqual(bot.pending_upi_payment(42, "chat")["payment_id"], "pay-5")
        self.assertIsNone(bot.pending_upi_payment(42, "video"))

if __name__ == "__main__":
    unittest.main()
