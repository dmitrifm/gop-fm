import re

PHRASE_LENGTH: int = 200


def split(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    sent_pattern = r"[^!?]+[!?]|[^!?]+$"
    sentences = [
        match.group(0).strip()
        for match in re.finditer(sent_pattern, text)
    ]

    out: list[str] = []

    for sentence in sentences:
        rest = sentence

        while len(rest) > PHRASE_LENGTH:
            # Сначала пытаемся разрезать после последней запятой перед лимитом.
            comma_pos = rest.rfind(",", 0, PHRASE_LENGTH + 1)

            if comma_pos >= 0:
                # Оставляем запятую в текущем куске.
                cut_pos = comma_pos + 1
            else:
                # Запятой нет — ищем последний пробел перед лимитом.
                space_pos = rest.rfind(" ", 0, PHRASE_LENGTH + 1)

                if space_pos > 0:
                    cut_pos = space_pos
                else:
                    # Одно огромное слово без пробелов — режем жёстко.
                    cut_pos = PHRASE_LENGTH

            chunk = rest[:cut_pos].strip()
            if chunk:
                out.append(chunk)

            rest = rest[cut_pos:].lstrip()

        if rest:
            out.append(rest)

    return out


if __name__ == "__main__":
    text = (
        "Привет! Братан, чё как дела? "
        "Это очень длинное предложение, в котором есть несколько логических частей, "
        "и при разбиении текста для синтеза речи желательно сначала искать запятую, "
        "чтобы голос сохранил нормальную интонацию и не делал паузу в каком-то странном месте. "
        "Внатуре всё чётко!"
    )

    for phrase in split(text):
        print(f"[{len(phrase)}] {phrase}")