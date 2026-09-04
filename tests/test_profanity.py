import asyncio
import os
import unittest
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import profanity
import database


class TestProfanityDetector(unittest.TestCase):

    def setUp(self):
        # Use full seed words list from database for realistic testing
        self.sample_words = database.DEFAULT_SEED_WORDS

    def test_normalization(self):
        self.assertEqual(profanity.normalize_text("П.И.З.Д.А"), "пизда")
        self.assertEqual(profanity.normalize_text("п*и*з*д*а"), "пизда")
        self.assertEqual(profanity.normalize_text("п-и-з-д-а"), "пизда")
        self.assertEqual(profanity.normalize_text("з4еб4л"), "заебал")
        self.assertEqual(profanity.normalize_text("6лядь"), "блядь")
        self.assertEqual(profanity.normalize_text("п и з д а"), "пизда")

    def test_profanity_detection(self):
        # Direct profanity
        is_profane, matched = profanity.contains_profanity("Это просто пиздец какой-то", self.sample_words)
        self.assertTrue(is_profane)

        # Obfuscated profanity
        is_profane, matched = profanity.contains_profanity("Какого х*у*я произошли изменения", self.sample_words)
        self.assertTrue(is_profane)

        is_profane, matched = profanity.contains_profanity("Ты меня з4еб4л полностью", self.sample_words)
        self.assertTrue(is_profane)

        is_profane, matched = profanity.contains_profanity("п.и.з.д.а наступила всему", self.sample_words)
        self.assertTrue(is_profane)

    def test_false_positives(self):
        # Harmless support chat messages containing words with sub-letters
        is_profane, _ = profanity.contains_profanity("Я хочу высказать свои переживания и эмоции без оскорблений", self.sample_words)
        self.assertFalse(is_profane)

        is_profane, _ = profanity.contains_profanity("Мне нужно отправить ответ до 18:00 в рублях", self.sample_words)
        self.assertFalse(is_profane)

        is_profane, _ = profanity.contains_profanity("У меня сильное колебание настроения сегодня", self.sample_words)
        self.assertFalse(is_profane)

        is_profane, _ = profanity.contains_profanity("Спасибо вам за помощь и поддержку!", self.sample_words)
        self.assertFalse(is_profane)


class TestDatabaseOperations(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.test_db = "test_temp_bot.db"
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except OSError:
                pass
        await database.init_db(self.test_db)

    async def asyncTearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except OSError:
                pass

    async def test_db_seeding_and_word_management(self):
        words = await database.get_words(self.test_db)
        self.assertGreater(len(words), 10)
        self.assertIn("хуй", words)

        # Add word
        added = await database.add_word(self.test_db, "новоеслово")
        self.assertTrue(added)
        words_after = await database.get_words(self.test_db)
        self.assertIn("новоеслово", words_after)

        # Remove word
        removed = await database.remove_word(self.test_db, "новоеслово")
        self.assertTrue(removed)
        words_final = await database.get_words(self.test_db)
        self.assertNotIn("новоеслово", words_final)

    async def test_violations_ladder(self):
        user_id = 99999
        chat_id = -100123456789
        count1 = await database.record_violation(self.test_db, user_id, "@testuser", chat_id=chat_id)
        self.assertEqual(count1, 1)

        count2 = await database.record_violation(self.test_db, user_id, "@testuser", chat_id=chat_id)
        self.assertEqual(count2, 2)

        data = await database.get_user_violation(self.test_db, user_id)
        self.assertEqual(data["violation_count"], 2)
        self.assertEqual(data["chat_id"], chat_id)

    async def test_get_user_id_by_username(self):
        user_id = 88888
        await database.record_violation(self.test_db, user_id, "@SpecialAdminUser")
        
        # Test with @ prefix
        found_id_1 = await database.get_user_id_by_username(self.test_db, "@specialadminuser")
        self.assertEqual(found_id_1, user_id)
        
        # Test without @ prefix
        found_id_2 = await database.get_user_id_by_username(self.test_db, "SpecialAdminUser")
        self.assertEqual(found_id_2, user_id)
        
        # Test non-existent
        not_found = await database.get_user_id_by_username(self.test_db, "nonexistent")
        self.assertIsNone(not_found)

    async def test_expired_bans_includes_chat_id(self):
        from datetime import datetime, timezone, timedelta
        user_id = 77777
        chat_id = -1009999999
        past_time = datetime.now(timezone.utc) - timedelta(days=1)
        
        await database.record_violation(self.test_db, user_id, "@banneduser", chat_id=chat_id)
        await database.set_banned_until(self.test_db, user_id, past_time, chat_id=chat_id)
        
        expired = await database.get_expired_bans(self.test_db)
        user_entry = next((u for u in expired if u["user_id"] == user_id), None)
        self.assertIsNotNone(user_entry)
        self.assertEqual(user_entry["chat_id"], chat_id)

    async def test_legacy_schema_migration(self):
        legacy_db = "test_legacy_migration.db"
        if os.path.exists(legacy_db):
            os.remove(legacy_db)
            
        try:
            # Create old-format violations table without chat_id
            import aiosqlite
            async with aiosqlite.connect(legacy_db) as db:
                await db.execute("""
                    CREATE TABLE violations (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        violation_count INTEGER DEFAULT 0,
                        last_violation_at TIMESTAMP,
                        banned_until TIMESTAMP
                    );
                """)
                await db.execute("INSERT INTO violations (user_id, username, violation_count) VALUES (12345, '@legacy', 1)")
                await db.commit()
                
            # Run init_db which should perform auto-migration
            success = await database.init_db(legacy_db)
            self.assertTrue(success)
            
            # Check that chat_id column was added and existing record preserved
            user_data = await database.get_user_violation(legacy_db, 12345)
            self.assertIsNotNone(user_data)
            self.assertEqual(user_data["username"], "@legacy")
            self.assertIn("chat_id", user_data)
            self.assertIsNone(user_data["chat_id"])
        finally:
            if os.path.exists(legacy_db):
                os.remove(legacy_db)


class TestWordCache(unittest.TestCase):

    def setUp(self):
        profanity.invalidate_cache()

    def tearDown(self):
        profanity.invalidate_cache()

    def test_cache_lifecycle(self):
        self.assertIsNone(profanity.get_cached_words())
        
        words = ["мат1", "мат2"]
        profanity.set_cached_words(words)
        self.assertEqual(profanity.get_cached_words(), ["мат1", "мат2"])
        
        profanity.add_cached_word("мат3")
        self.assertIn("мат3", profanity.get_cached_words())
        
        profanity.remove_cached_word("мат1")
        self.assertNotIn("мат1", profanity.get_cached_words())
        
        profanity.invalidate_cache()
        self.assertIsNone(profanity.get_cached_words())


class TestAdminConfig(unittest.TestCase):

    def test_is_admin_check(self):
        from handlers.admin import is_admin
        import config
        
        original_admin_ids = config.ADMIN_IDS
        original_admin_id = config.ADMIN_ID
        try:
            config.ADMIN_IDS = {111, 222, 333}
            config.ADMIN_ID = 111
            
            self.assertTrue(is_admin(111))
            self.assertTrue(is_admin(222))
            self.assertTrue(is_admin(333))
            self.assertFalse(is_admin(444))
        finally:
            config.ADMIN_IDS = original_admin_ids
            config.ADMIN_ID = original_admin_id


class TestModerationNotifications(unittest.IsolatedAsyncioTestCase):

    async def test_notify_admin_missing_rights_safe_handling(self):
        from unittest.mock import AsyncMock, MagicMock
        from moderation import notify_admin_missing_rights
        import config

        orig_ids = config.ADMIN_IDS
        orig_id = config.ADMIN_ID
        try:
            config.ADMIN_IDS = {99901, 99902}
            context = MagicMock()
            context.bot.send_message = AsyncMock()

            # Test with None chat_title
            await notify_admin_missing_rights(context, "удаление", None)
            self.assertEqual(context.bot.send_message.call_count, 2)

            # Test with special characters in chat_title and action
            context.bot.send_message.reset_mock()
            await notify_admin_missing_rights(context, "<кик & бан>", "Чат <Support> & 'Friends'")
            self.assertEqual(context.bot.send_message.call_count, 2)
            sent_text = context.bot.send_message.call_args[1]["text"]
            self.assertIn("&lt;Support&gt; &amp; &#x27;Friends&#x27;", sent_text)
        finally:
            config.ADMIN_IDS = orig_ids
            config.ADMIN_ID = orig_id


if __name__ == "__main__":
    unittest.main()

