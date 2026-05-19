import unittest

from app.text_normalization import normalize_text


class NormalizeTextTests(unittest.TestCase):
    def test_plain_integer_in_russian(self) -> None:
        self.assertEqual(
            normalize_text("Сегодня 2025 новостей.", "ru"),
            "Сегодня две тысячи двадцать пять новостей.",
        )

    def test_decimal_in_russian(self) -> None:
        self.assertEqual(
            normalize_text("Температура 36.6 градуса.", "ru"),
            "Температура тридцать шесть точка шесть градуса.",
        )

    def test_leading_zeroes_are_spoken_digit_by_digit(self) -> None:
        self.assertEqual(
            normalize_text("Код 007 принят.", "ru"),
            "Код ноль ноль семь принят.",
        )

    def test_non_russian_text_is_left_unchanged(self) -> None:
        self.assertEqual(
            normalize_text("Invoice 2025 is ready.", "en"),
            "Invoice 2025 is ready.",
        )


if __name__ == "__main__":
    unittest.main()
