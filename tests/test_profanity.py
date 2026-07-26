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
        count1 = await database.record_violation(self.test_db, user_id, "@testuser")
        self.assertEqual(count1, 1)

        count2 = await database.record_violation(self.test_db, user_id, "@testuser")
        self.assertEqual(count2, 2)

        data = await database.get_user_violation(self.test_db, user_id)
        self.assertEqual(data["violation_count"], 2)


if __name__ == "__main__":
    unittest.main()
