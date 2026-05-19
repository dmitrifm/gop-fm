import re

_RU_ONES = {
    0: "ноль",
    1: "один",
    2: "два",
    3: "три",
    4: "четыре",
    5: "пять",
    6: "шесть",
    7: "семь",
    8: "восемь",
    9: "девять",
    10: "десять",
    11: "одиннадцать",
    12: "двенадцать",
    13: "тринадцать",
    14: "четырнадцать",
    15: "пятнадцать",
    16: "шестнадцать",
    17: "семнадцать",
    18: "восемнадцать",
    19: "девятнадцать",
}

_RU_TENS = {
    20: "двадцать",
    30: "тридцать",
    40: "сорок",
    50: "пятьдесят",
    60: "шестьдесят",
    70: "семьдесят",
    80: "восемьдесят",
    90: "девяносто",
}

_RU_HUNDREDS = {
    100: "сто",
    200: "двести",
    300: "триста",
    400: "четыреста",
    500: "пятьсот",
    600: "шестьсот",
    700: "семьсот",
    800: "восемьсот",
    900: "девятьсот",
}

_RU_GROUPS: list[tuple[str, str, str, str | None]] = [
    ("", "", "", None),
    ("тысяча", "тысячи", "тысяч", "feminine"),
    ("миллион", "миллиона", "миллионов", None),
    ("миллиард", "миллиарда", "миллиардов", None),
    ("триллион", "триллиона", "триллионов", None),
]

_NUMBER_PATTERN = re.compile(r"(?<![\w/])[-+]?\d+(?:[.,]\d+)?(?![\w/])")


def normalize_text(text: str, language_id: str) -> str:
    normalized_language_id = language_id.strip().lower()
    if not normalized_language_id.startswith("ru"):
        return text
    return _NUMBER_PATTERN.sub(_normalize_ru_number_match, text)


def _normalize_ru_number_match(match: re.Match[str]) -> str:
    token = match.group(0)
    sign = ""
    if token.startswith(("-", "+")):
        sign = "минус " if token.startswith("-") else "плюс "
        token = token[1:]

    if "," in token or "." in token:
        separator = "запятая" if "," in token else "точка"
        integer_part, fractional_part = re.split(r"[.,]", token, maxsplit=1)
        integer_words = _ru_integer_to_words(integer_part or "0")
        fractional_words = _ru_digits_to_words(fractional_part)
        return f"{sign}{integer_words} {separator} {fractional_words}"

    return f"{sign}{_ru_integer_to_words(token)}"


def _ru_integer_to_words(token: str) -> str:
    stripped = token.lstrip("0")
    if not stripped:
        return " ".join(_RU_ONES[0] for _ in token) if token else _RU_ONES[0]
    if len(token) > 1 and token.startswith("0"):
        return _ru_digits_to_words(token)

    value = int(stripped)
    if value == 0:
        return _RU_ONES[0]

    parts: list[str] = []
    group_index = 0
    while value > 0:
        value, remainder = divmod(value, 1000)
        if remainder:
            group_words = _ru_triplet_to_words(remainder, group_index)
            group_name = _ru_group_name(remainder, group_index)
            if group_name:
                group_words.append(group_name)
            parts.append(" ".join(group_words))
        group_index += 1

    return " ".join(reversed(parts))


def _ru_triplet_to_words(value: int, group_index: int) -> list[str]:
    words: list[str] = []
    hundreds = value // 100 * 100
    tens_ones = value % 100
    tens = tens_ones // 10 * 10
    ones = tens_ones % 10

    if hundreds:
        words.append(_RU_HUNDREDS[hundreds])
    if 0 < tens_ones < 20:
        words.append(_ru_one_word(tens_ones, group_index))
        return words
    if tens:
        words.append(_RU_TENS[tens])
    if ones:
        words.append(_ru_one_word(ones, group_index))
    return words


def _ru_one_word(value: int, group_index: int) -> str:
    if group_index == 1:
        if value == 1:
            return "одна"
        if value == 2:
            return "две"
    return _RU_ONES[value]


def _ru_group_name(value: int, group_index: int) -> str:
    if group_index == 0 or group_index >= len(_RU_GROUPS):
        return ""
    singular, paucal, plural, _ = _RU_GROUPS[group_index]
    last_two = value % 100
    last_one = value % 10
    if 11 <= last_two <= 14:
        return plural
    if last_one == 1:
        return singular
    if 2 <= last_one <= 4:
        return paucal
    return plural


def _ru_digits_to_words(token: str) -> str:
    return " ".join(_RU_ONES[int(char)] for char in token if char.isdigit())
