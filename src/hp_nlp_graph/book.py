import pickle
import time

from tqdm import tqdm

from .coreference import (
    coref_resolve_and_get_characters_matches_in_chapter,
    get_interactions,
)
from .language import FastCoref, add_entity_ruler, get_coref_resolver_nlp
from .neo4j import add_characters_to_neo4j, add_interactions_to_neo4j
from .scraper import Chapter, get_characters_by_chapter
from .utils import get_characters_seen_till_chapter


class Book:
    """A class to represent a Harry Potter book. It contains the book number and the url to the character index page.
    It also contains a list of Chapter objects, each of which contains a list of Character objects.
    It contains methods to scrape the character index page and enrich the characters with additional information.
    It also contains methods to save the list of Chapter objects and to add the characters to a Neo4j database.

    Its intended usage workflow is as follows:
    ```python
    book = Book(book_number, character_index_url)
    book.set_chapters_with_characters()
    book.save_chapters_with_characters()
    book.add_characters_to_neo4j(driver)
    ```
    """

    def __init__(self, book_number: int, character_index_url: str, book_text_path: str):
        self.book_number = book_number
        self.character_index_url = character_index_url
        self.book_text_path = book_text_path
        self.chapters_with_characters = None
        self.chapters_with_characters_dict = None
        self.base_nlp = None
        self.nlp = None
        self.coref = None
        self.chapter_texts = None
        self.matches_by_chapter = None
        self.interactions_by_chapter = None

    def _scrape_chapters_with_characters(self) -> list[Chapter]:
        return get_characters_by_chapter(self.character_index_url)

    def _enrich_characters(self) -> None:
        for chapter in self.chapters_with_characters:
            for character in chapter.characters:
                time.sleep(1)
                character.enrich()

    def set_chapters_with_characters(self, reset: bool = False) -> None:
        if self.chapters_with_characters is not None or reset:
            self.chapters_with_characters = self._scrape_chapters_with_characters()
            self.chapters_with_characters_dict = {
                chapter.number: chapter for chapter in self.chapters_with_characters
            }
            self._enrich_characters()

    def save_chapters_with_characters(self, path: str = None) -> None:
        if self.chapters_with_characters is None:
            raise ValueError("No chapters with characters have been set.")
        if path is None:
            path = f"book/{self.book_number}/chapter_characters.pkl"
        with open(path, "wb") as f:
            pickle.dump(self.chapters_with_characters, f)

    def add_characters_to_neo4j(self, driver) -> None:
        if self.chapters_with_characters is None:
            raise ValueError("No chapters with characters have been set.")
        add_characters_to_neo4j(driver, self.chapters_with_characters)

    @property
    def all_characters(self) -> list:
        if self.chapters_with_characters is None:
            raise ValueError("No chapters with characters have been set.")
        return [
            character
            for chapter in self.chapters_with_characters
            for character in chapter.characters
        ]

    def _initialize_coreference_resolver(self, device="cuda:0") -> None:
        # Initialize the language models
        base_nlp, nlp = get_coref_resolver_nlp(device=device)
        # Add entity rulers to the language models using the character names
        self.base_nlp = add_entity_ruler(base_nlp, self.all_characters)
        self.nlp = add_entity_ruler(nlp, self.all_characters)
        # Initialize the coreference resolver
        self.coref = FastCoref(base_nlp, nlp)

    def _open_book_text(self) -> str:
        with open(self.book_text_path, "r") as f:
            return f.read().split("CHAPTER ")[1:]

    def coreference_resolve(self, device="cuda:0") -> None:
        if self.coref is None or self.base_nlp is None or self.nlp is None:
            self._initialize_coreference_resolver(device=device)
        if self.chapter_texts is None:
            self.chapter_texts = self._open_book_text()
        matches_by_chapter = {}
        for chapter_number, chapter_text in enumerate(self.chapter_texts):
            (
                matches,
                resolved_docs,
            ) = coref_resolve_and_get_characters_matches_in_chapter(
                base_nlp=self.base_nlp,
                nlp=self.nlp,
                chapter_text=chapter_text,
                characters_seen_till_this_chapter=get_characters_seen_till_chapter(
                    self.book_number, chapter_number + 1
                ),
                coref_resolver=self.coref.resolve,
            )
            matches_by_chapter[chapter_number + 1] = matches
        self.matches_by_chapter = matches_by_chapter

    def save_coreference_resolution(self, path: str = None) -> None:
        if self.matches_by_chapter is None:
            raise ValueError("No coreference resolution has been done.")
        if path is None:
            path = f"book/{self.book_number}/coreference_resolution_by_chapter.pkl"
        with open(path, "wb") as f:
            pickle.dump(self.matches_by_chapter, f)

    def calculate_interactions(self, thresh: int = 14):
        if self.matches_by_chapter is None:
            raise ValueError("No coreference resolution has been done.")
        interactions_by_chapter = {}
        for chapter_number, matches in self.matches_by_chapter.items():
            interactions_by_chapter[chapter_number] = get_interactions(
                matches, thresh=thresh
            )
        self.interactions_by_chapter = interactions_by_chapter

    def save_interactions(self, path: str = None) -> None:
        if self.interactions_by_chapter is None:
            raise ValueError("No interactions have been calculated.")
        if path is None:
            path = f"book/{self.book_number}/interactions_by_chapter.pkl"
        with open(path, "wb") as f:
            pickle.dump(self.interactions_by_chapter, f)

    def add_interactions_to_neo4j(self, driver) -> None:
        if self.interactions_by_chapter is None:
            raise ValueError("No interactions have been calculated.")
        for interactions in tqdm(self.interactions_by_chapter.values()):
            add_interactions_to_neo4j(driver, interactions)

    # TODO: Add methods to add node metrics to Neo4j
