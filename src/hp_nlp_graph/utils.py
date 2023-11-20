from .scraper import Character


def get_characters_seen_till_chapter(
    chapter_characters: dict, book: int, chapter: int
) -> list[Character]:
    """Get all characters seen till a given chapter in a given book.

    Args:
        chapter_characters (dict): A dictionary containing all characters seen in a chapter. It is of the form {book_number: {chapter_number: [Character]}}.
        book (int): The book number.
        chapter (int): The chapter number.

    Returns:
        list[Character]: A list of characters seen till the given chapter in the given book.
    """
    required_characters = list()
    for book_number, chapters in chapter_characters.items():
        if book_number > book:
            continue
        for chapter_number, characters in chapters.items():
            if book_number == book and chapter_number > chapter:
                continue
            for character in characters:
                required_characters.append(character)

    return required_characters
