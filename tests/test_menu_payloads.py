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


class SuccessfulPaymentResilienceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        handle.close()
        self.database_path = handle.name
        self.original_database_path = bot.DATABASE_PATH
        self.original_payment_channel_id = bot.PAYMENT_CHANNEL_ID
        self.original_private_chat_group_id = bot.PRIVATE_CHAT_GROUP_ID
        bot.DATABASE_PATH = self.database_path
        bot.PAYMENT_CHANNEL_ID = -100777000111
        bot.PRIVATE_CHAT_GROUP_ID = -100888000222
        bot.init_db()

    def tearDown(self):
        bot.DATABASE_PATH = self.original_database_path
        bot.PAYMENT_CHANNEL_ID = self.original_payment_channel_id
        bot.PRIVATE_CHAT_GROUP_ID = self.original_private_chat_group_id
        gc.collect()
        os.unlink(self.database_path)

    def direct_tip_message(self, answer):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            successful_payment=SimpleNamespace(
                invoice_payload="topicoffer_tip-token",
                total_amount=2500,
                telegram_payment_charge_id="charge-2500",
            ),
            answer=answer,
        )

    def insert_direct_tip(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO topic_offers
                (token, session_code, customer_id, stars, duration_hours,
                 description, status, created_at, origin_chat_id,
                 origin_dm_topic_id, created_by)
                VALUES ('tip-token', 'DM-1-2', 42, 2500, 0, 'Tip', 'pending',
                        'now', -1004329721962, 98765, 7)"""
            )

    def private_tip_message(self, answer):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            successful_payment=SimpleNamespace(
                invoice_payload="offer_private-token",
                total_amount=2500,
                telegram_payment_charge_id="charge-private-2500",
            ),
            answer=answer,
        )

    def insert_private_tip(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO private_offers
                (token, created_by, stars, duration_hours, status, claimed_by,
                 created_at, description)
                VALUES ('private-token', 7, 2500, 0, 'pending', 42, 'now', 'Tip')"""
            )

    async def test_blocked_customer_cannot_stop_private_tip_reporting(self):
        self.insert_private_tip()
        blocked = bot.TelegramForbiddenError(method=None, message="bot was blocked by the user")
        message = self.private_tip_message(AsyncMock(side_effect=blocked))

        with patch.object(bot.bot, "send_message", AsyncMock()) as send_message:
            with patch.object(bot, "send_sales_update", AsyncMock(return_value=True)) as sales_update:
                await bot.successful_payment(message)

        message.answer.assert_awaited_once_with("✅ Tip received. Thank you!")
        send_message.assert_awaited_once()
        self.assertEqual(send_message.await_args.args[0], -100777000111)
        self.assertIn("CUSTOM TIP PAID", send_message.await_args.args[1])
        sales_update.assert_awaited_once_with("Custom tip · 2,500 Stars")

        with bot.db_connect() as connection:
            offer = connection.execute(
                "SELECT status FROM private_offers WHERE token='private-token'"
            ).fetchone()
            payments = connection.execute(
                "SELECT * FROM stars_payments WHERE telegram_charge_id='charge-private-2500'"
            ).fetchall()
        self.assertEqual(offer["status"], "active")
        self.assertEqual(len(payments), 1)

    async def test_blocked_customer_cannot_stop_direct_confirmation(self):
        self.insert_direct_tip()
        blocked = bot.TelegramForbiddenError(method=None, message="bot was blocked by the user")
        message = self.direct_tip_message(AsyncMock(side_effect=blocked))

        with patch.object(bot.bot, "send_message", AsyncMock()) as send_message:
            with patch.object(bot, "send_sales_update", AsyncMock(return_value=True)) as sales_update:
                await bot.successful_payment(message)

        message.answer.assert_awaited_once_with("✅ Payment received. Thank you!")
        self.assertEqual(send_message.await_count, 2)
        direct_notice = send_message.await_args_list[0]
        self.assertEqual(direct_notice.args[0], -1004329721962)
        self.assertEqual(direct_notice.kwargs["direct_messages_topic_id"], 98765)
        self.assertIn("2,500 Stars paid", direct_notice.args[1])
        self.assertEqual(send_message.await_args_list[1].args[0], -100777000111)
        sales_update.assert_awaited_once_with("Custom offer · 2,500 Stars")

        with bot.db_connect() as connection:
            offer = connection.execute(
                "SELECT status FROM topic_offers WHERE token='tip-token'"
            ).fetchone()
            payments = connection.execute(
                "SELECT * FROM stars_payments WHERE telegram_charge_id='charge-2500'"
            ).fetchall()
        self.assertEqual(offer["status"], "paid")
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]["stars"], 2500)

    async def test_direct_notice_failure_does_not_stop_admin_or_sales(self):
        self.insert_direct_tip()
        message = self.direct_tip_message(AsyncMock())
        direct_error = bot.TelegramBadRequest(method=None, message="direct topic unavailable")
        send_message = AsyncMock(side_effect=[direct_error, None])

        with patch.object(bot.bot, "send_message", send_message):
            with patch.object(bot, "send_sales_update", AsyncMock(return_value=True)) as sales_update:
                await bot.successful_payment(message)

        self.assertEqual(send_message.await_count, 2)
        self.assertEqual(send_message.await_args_list[1].args[0], -100777000111)
        message.answer.assert_awaited_once_with("✅ Payment received. Thank you!")
        sales_update.assert_awaited_once_with("Custom offer · 2,500 Stars")

    async def test_normal_direct_payment_posts_every_confirmation(self):
        self.insert_direct_tip()
        message = self.direct_tip_message(AsyncMock())

        with patch.object(bot.bot, "send_message", AsyncMock()) as send_message:
            with patch.object(bot, "send_sales_update", AsyncMock(return_value=True)) as sales_update:
                await bot.successful_payment(message)

        self.assertEqual(send_message.await_count, 2)
        message.answer.assert_awaited_once_with("✅ Payment received. Thank you!")
        sales_update.assert_awaited_once()

class PaymentHandoffTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        handle.close()
        self.database_path = handle.name
        self.original_database_path = bot.DATABASE_PATH
        self.original_review_chat_id = bot.ADMIN_REVIEW_CHAT_ID
        self.original_topic_id = bot.PAYMENT_FULFILMENT_TOPIC_ID
        self.original_private_chat_group_id = bot.PRIVATE_CHAT_GROUP_ID
        bot.DATABASE_PATH = self.database_path
        bot.ADMIN_REVIEW_CHAT_ID = -1004438876540
        bot.PRIVATE_CHAT_GROUP_ID = -1004438876540
        bot.PAYMENT_FULFILMENT_TOPIC_ID = 77
        bot.init_db()

    def tearDown(self):
        bot.DATABASE_PATH = self.original_database_path
        bot.ADMIN_REVIEW_CHAT_ID = self.original_review_chat_id
        bot.PAYMENT_FULFILMENT_TOPIC_ID = self.original_topic_id
        bot.PRIVATE_CHAT_GROUP_ID = self.original_private_chat_group_id
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

    async def test_topic_tip_allows_15000_stars(self):
        session_code = "CHAT-150000"
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO private_sessions
                (session_code, offer_token, customer_id, operator_id, starts_at,
                 expires_at, status, topic_thread_id)
                VALUES (?, ?, 42, 7, 'now', '2999-01-01T00:00:00+05:30',
                        'active', 77)""",
                (session_code, "offer-token"),
            )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=7),
            chat=SimpleNamespace(id=-1004438876540),
            message_thread_id=77,
            answer=AsyncMock(),
        )
        command = SimpleNamespace(args="15000 Video call")
        with patch.object(bot, "is_tip_operator", return_value=True):
            with patch.object(bot.bot, "send_invoice", AsyncMock()) as send_invoice:
                await bot.create_topic_offer(message, command, extend=False)

        send_invoice.assert_awaited_once()
        self.assertEqual(send_invoice.await_args.kwargs["chat_id"], 42)
        self.assertEqual(send_invoice.await_args.kwargs["prices"][0].amount, 15000)
        message.answer.assert_awaited_once()
        self.assertIn("15,000 Stars", message.answer.await_args.args[0])

    async def test_customer_relay_does_not_send_repeated_session_header(self):
        with bot.db_connect() as connection:
            connection.execute(
                """INSERT INTO private_sessions
                (session_code, offer_token, customer_id, operator_id, starts_at,
                 expires_at, status, topic_thread_id)
                VALUES ('CHAT-301214', 'offer-token', 42, 7, 'now',
                        '2999-01-01T00:00:00+05:30', 'active', 77)"""
            )
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            chat=SimpleNamespace(id=42),
            message_id=555,
        )
        copied = SimpleNamespace(message_id=777)
        with patch.object(bot.bot, "send_message", AsyncMock()) as send_message:
            with patch.object(bot.bot, "copy_message", AsyncMock(return_value=copied)) as copy_message:
                self.assertTrue(await bot.relay_private_message(message))

        send_message.assert_not_awaited()
        copy_message.assert_awaited_once()
        with bot.db_connect() as connection:
            mappings = connection.execute("SELECT * FROM relay_messages").fetchall()
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["operator_message_id"], 777)

if __name__ == "__main__":
    unittest.main()
