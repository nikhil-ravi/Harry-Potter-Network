from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://harrypotter.fandom.com"
CHARACTERS_LIST_URL_EXAMPLE = (
    BASE_URL + "/wiki/Harry_Potter_and_the_Philosopher%27s_Stone_(character_index)"
)


def get_aliases(soup: BeautifulSoup) -> list[str]:
    """Gets a list of aliases for a character.

    Args:
        soup (BeautifulSoup): The soup object for the character's page.

    Returns:
        list[str]: A list of aliases for the character.
    """
    aliases_list = []
    aliases = soup.find("div", attrs={"data-source": "alias"}).findAll("li")
    for a in aliases:
        if "disguise" in a.text or "the name he told" in a.text:
            continue
        aliases_list.append(a.text.split("[")[0].split("(")[0].strip())
    return aliases_list


def get_loyalties(soup: BeautifulSoup) -> list[str]:
    """Gets a list of loyalties for a character.

    Args:
        soup (BeautifulSoup): The soup object for the character's page.

    Returns:
        list[str]: A list of loyalties for the character.
    """
    loyalties_list = []
    loyalties = soup.find("div", attrs={"data-source": "loyalty"}).findAll("li")
    for l in loyalties:
        if not l.find("ul"):
            loyalties_list.append(l.text.split("[")[0].split("(")[0].strip())
        else:
            loyalties_list.append(l.find("a").text.split("[")[0].split("(")[0].strip())

    return loyalties_list


def get_family_relationships(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Gets a list of family relationships for a character.

    Args:
        soup (BeautifulSoup): The soup object for the character's page.

    Returns:
        list[dict[str, str]]: A list of family relationships for the character.
    """
    relationships_list = []
    relationships = soup.find("div", attrs={"data-source": "family"}).findAll("li")
    for rel in relationships:
        character = rel.text.split("[")[0].split("(")[0].strip()
        rel_type = rel.text.split("(")[-1].split(")")[0].split("[")[0]
        relationships_list.append({"person": character, "type": rel_type})
    return relationships_list


def get_field(soup: BeautifulSoup, field_name: str) -> str:
    """Gets a field for a character.

    Args:
        soup (BeautifulSoup): The soup object for the character's page.
        field_name (str): The name of the field to get.

    Returns:
        str: The value of the field.
    """
    field_value = (
        soup.find("div", attrs={"data-source": field_name})
        .find("div")
        .text.split("[")[0]
        .split("(")[0]
        .strip()
    )
    return field_value


ATTRIBUTES_TO_SCRAPE = [
    ("aliases", get_aliases),
    ("loyalties", get_loyalties),
    ("family_relations", get_family_relationships),
    ("blood_status", lambda soup: get_field(soup, "blood")),
    ("nationality", lambda soup: get_field(soup, "nationality")),
    ("species", lambda soup: get_field(soup, "species")),
    ("house", lambda soup: get_field(soup, "house")),
    ("gender", lambda soup: get_field(soup, "gender")),
]


@dataclass
class Character:
    """Represents a Harry Potter character with associated attributes."""

    title: str
    href: str
    aliases: list = None
    loyalties: list = None
    famliy_relations: list = None
    blood_status: str = None
    nationality: str = None
    species: str = None
    house: str = None
    gender: str = None

    def set_attr(self, attr: str, value):
        """Sets the value of an attribute.

        Args:
            attr (str): The name of the attribute to set.
            value (_type_): The value to set the attribute to.
        """
        setattr(self, attr, value)

    def enrich(self) -> None:
        """Adds additional information to a character.

        Args:
            character (Character): The character to add information to.
        """
        res = requests.get(BASE_URL + self.href).text
        soup = BeautifulSoup(res, "html.parser")
        for attr_name, scraper_func in ATTRIBUTES_TO_SCRAPE:
            try:
                value = scraper_func(soup)
                self.set_attr(attr_name, value)
            except Exception as e:
                pass


@dataclass
class Chapter:
    """Represents a chapter in a Harry Potter book and the characters mentioned in it."""

    chapter: int
    characters: list[Character]


def get_characters_by_chapter(url: str = CHARACTERS_LIST_URL_EXAMPLE) -> list[Chapter]:
    """Gets a list of chapters and the characters mentioned in them.

    Returns:
        list[Chapter]: A list of chapters and the characters mentioned in them.
    """
    res = requests.get(url).text
    soup = BeautifulSoup(res, "html.parser")
    div = soup.find_all("div", class_="mw-parser-output")
    chapter_sections = div[0].find_all("h2")
    chapters = []
    chapter_idx = 1
    for chapter_section in chapter_sections:
        try:
            chapter_name = chapter_section.find("span", class_="mw-headline").text
            if not (
                chapter_name.startswith("Chapter")
                or chapter_name.startswith("Epilogue")
            ):
                continue
        except AttributeError:
            continue

        next_sibling = chapter_section.find_next_sibling()
        if next_sibling.name == "ul":
            list_of_characters = []
            for li in next_sibling.find_all("li"):
                character = li.find("a")
                if not character or not character.get("title"):
                    continue
                list_of_characters.append(
                    Character(title=character.get("title"), href=character.get("href"))
                )
            chapters.append(Chapter(chapter=chapter_idx, characters=list_of_characters))
            chapter_idx += 1
        elif next_sibling.name == "table":
            list_of_characters = []
            for tr in next_sibling.find_all("tr"):
                td = tr.find("td")
                character = td.find("a")
                if not character or not character.get("title"):
                    continue
                list_of_characters.append(
                    Character(title=character.get("title"), href=character.get("href"))
                )
            chapters.append(Chapter(chapter=chapter_idx, characters=list_of_characters))
            chapter_idx += 1
        elif next_sibling.name == "dl":  # For chapters with no new characters
            chapters.append(Chapter(chapter=chapter_idx, characters=[]))
            chapter_idx += 1
        elif (
            next_sibling.name == "p"
        ):  # For some chapters (Book 6: Chapter 25) with no new characters
            chapters.append(Chapter(chapter=chapter_idx, characters=[]))
            chapter_idx += 1
    return chapters
