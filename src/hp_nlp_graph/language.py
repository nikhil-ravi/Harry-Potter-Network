from dataclasses import dataclass
from typing import Literal, get_args

import spacy
import spacy_experimental
from fastcoref import LingMessCoref, spacy_component
from spacy.language import Language
from spacy.tokens import Doc

from .scraper import Character

NLP_TYPES = Literal["spacy", "fastcoref"]

STOP_WORDS = [
    "of",
    "the",
    "at",
    "family",
    "keeper",
    "wizard",
    "fat",
    "de",
    "hogwarts",
    "hotel",
    "owner",
    "express",
]

SHORT_FORMS = {
    "Ronald": "ron",
    "William": "bill",
    "Charles": "charlie",
    "Percy": "perce",
    "Ginevra": "ginny",
}


def get_coref_resolver_nlp(
    type: NLP_TYPES = "fastcoref", device: str = "cpu"
) -> tuple[Language, Language]:
    """Get Spacy NLP object with coreference resolution.

    Args:
        type (NLP_TYPES, optional): Type of NLP to use. Defaults to "fastcoref".
        device (str, optional): Device to run coreference resolution on. Defaults to "cpu".

    Raises:
        ValueError: If type is not "spacy" or "fastcoref"

    Returns:
        tuple[Language, Language]: Tuple of Spacy NLP objects. 1. Base NLP object, 2. NLP object with coreference resolution
    """
    if type not in get_args(NLP_TYPES):
        raise ValueError(f"Invalid type {type} for NLP")
    base_nlp = spacy.load("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")
    if type == "spacy":
        nlp_coref = spacy.load("en_coreference_web_trf")
        nlp_coref.replace_listeners("transformer", "coref", ["model.tok2vec"])
        nlp_coref.replace_listeners("transformer", "span_resolver", ["model.tok2vec"])

        nlp.add_pipe("coref", source=nlp_coref)
        nlp.add_pipe("span_resolver", source=nlp_coref)
    else:
        nlp.add_pipe(
            "fastcoref",
            config={
                "model_architecture": "LingMessCoref",
                "model_path": "biu-nlp/lingmess-coref",
                "device": device,
                "enable_progress_bar": False,
            },
        )
    return base_nlp, nlp


class SpacyCoref:
    """Spacy coreference resolver.

    Args:
        base_nlp (Language): Spacy Language object without coref and span_resolver
        nlp (Language): Spacy Language object with coref and span_resolver
        head_only_clusters (str, optional): Whether to use only the head of the coreference clusters. Defaults to False.
    """

    def __init__(
        self, base_nlp: Language, nlp: Language, head_only_clusters: bool = False
    ):
        self.nlp = nlp
        self.base_nlp = base_nlp
        self.head_only_clusters = head_only_clusters

    def resolve(self, text: str) -> Doc:
        """Resolve coreference clusters in document.

        Args:
            nlp (Language): Spacy Language object with coref and span_resolver
            text (str): Text to resolve coreferences in

        Returns:
            Doc: Spacy Doc with resolved coreferences
        """
        doc = self.nlp(text)

        token_mention_mapper = {}  # token_id: reference_text
        output_string = ""
        clusters = [
            val
            for key, val in doc.spans.items()
            if key.startswith(
                "coref_head_cluster" if self.head_only_clusters else "coref_cluster"
            )
        ]

        for cluster in clusters:
            first_mention = cluster[0]
            for mentions in list(cluster)[1:]:
                # Set the first_span.text for the first token in the token_mention_mapper
                token_mention_mapper[mentions[0].idx] = first_mention.text
                for token in mentions[1:]:
                    token_mention_mapper[token.idx] = ""

        # Loop through every token in the document
        for token in doc:
            if token.idx in token_mention_mapper:
                output_string += token_mention_mapper[token.idx] + token.whitespace_
            else:
                output_string += token.text + token.whitespace_

        return self.nlp(output_string)


class FastCoref:
    """Fastcoref coreference resolver.

    Args:
        base_nlp (Language): Spacy Language object without coref and span_resolver
        nlp (Language): Spacy Language object with coref and span_resolver
    """

    def __init__(self, base_nlp: Language, nlp: Language):
        self.nlp = nlp
        self.base_nlp = base_nlp

    def resolve(self, text: str) -> Doc:
        """Resolve coreference clusters in document.

        Args:
            text (str): Text to resolve coreferences in

        Returns:
            Doc: Spacy Doc with resolved coreferences
        """
        doc = self.nlp(text, component_cfg={"fastcoref": {"resolve_text": True}})
        return self.base_nlp(doc._.resolved_text)


@dataclass(frozen=True)
class EntityRulePattern:
    """Dataclass for entity ruler patterns.

    Args:
        label (str): Label of the Entity
        pattern (str): Pattern to match
    """

    label: str
    pattern: str

    def __eq__(self, __value: object) -> bool:
        """Check if two EntityRulePattern objects are equal.

        Args:
            __value (object): Object to compare to

        Returns:
            bool: Whether the two objects are equal
        """
        return self.pattern == __value.pattern and self.label == __value.label


def get_entity_ruler_patterns(character: Character) -> list[EntityRulePattern]:
    """Get entity ruler patterns for characters.

    Args:
        character: The character to get patterns for

    Returns:
        list: List of entity ruler patterns
    """
    ruler_patterns = []
    parts_of_name = [name for name in character.title.split(" ") if len(name) > 2]
    if not "'" in character.title:  # Skip names like "Hagrid's wife"
        ruler_patterns.append(
            EntityRulePattern(label="PERSON", pattern=character.title)
        )
        for part_of_name in parts_of_name:
            if part_of_name.lower() in STOP_WORDS:
                continue
            ruler_patterns.append(
                EntityRulePattern(label="PERSON", pattern=part_of_name)
            )
    return ruler_patterns


def add_entity_ruler(nlp: Language, characters: list[Character]) -> Language:
    """Add entity ruler to NLP object.

    Args:
        nlp (Language): Spacy NLP object
        characters (list[Character]): List of characters to add patterns for

    Returns:
        Language: Spacy NLP object with entity ruler
    """
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    patterns = [
        {
            "label": "PERSON",
            "pattern": "Mr. and Mrs. Dursley",
            "id": "Mr. and Mrs. Dursley",
        },
        {"label": "PERSON", "pattern": "Mr. Dursley", "id": "Mr. Dursley"},
        {"label": "PERSON", "pattern": "Mrs. Dursley", "id": "Mrs. Dursley"},
        {"label": "PERSON", "pattern": "Voldemort", "id": "Lord Voldemort"},
    ]
    ruler.add_patterns(patterns)
    ruler_patterns = []
    for character in characters:
        ruler_patterns.extend(get_entity_ruler_patterns(character))
    ruler.add_patterns([pattern.__dict__ for pattern in set(ruler_patterns)])
    return nlp


def get_matcher_patterns(character: Character) -> list:
    """Get matcher patterns for characters.

    Args:
        character: The character to get patterns for

    Returns:
        list: List of matcher patterns
    """
    matcher_patterns = []
    # Split the character's name into parts and filter out short parts
    parts_of_name = [name for name in character.title.split(" ") if len(name) > 2]
    # Add the whole name pattern
    matcher_patterns.append(
        [
            {"LOWER": part_of_name.lower(), "IS_TITLE": True}
            for part_of_name in parts_of_name
        ]
    )

    if not "'" in character.title:  # Skip names like "Hagrid's wife"
        for part_of_name in parts_of_name:
            if part_of_name.lower() in STOP_WORDS:
                continue

            # Add patterns for names without stopwords
            matcher_patterns.append(
                [
                    {"LOWER": part_of_name.lower(), "IS_TITLE": True},
                ]
            )

            # Define short forms for some names
            if part_of_name in SHORT_FORMS:
                short_form = SHORT_FORMS[part_of_name]
                matcher_patterns.append(
                    [
                        {"LOWER": short_form.lower(), "IS_TITLE": True},
                    ]
                )

            # Add patterns for names starting with "Mc" or "Mac"
            if part_of_name.startswith("Mc") or part_of_name.startswith("Mac"):
                matcher_patterns.append(
                    [
                        {"ORTH": part_of_name},
                    ]
                )

    # Add specific patterns for the character "Tom Riddle"
    if character.title == "Tom Riddle":
        matcher_patterns.append(
            [
                {"LOWER": "lord", "IS_TITLE": True},
                {"LOWER": "voldemort", "IS_TITLE": True},
            ]
        )
        matcher_patterns.append(
            [
                {"LOWER": "voldemort", "IS_TITLE": True},
            ]
        )
        matcher_patterns.append(
            [
                {"LOWER": "you", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "know", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "who", "IS_TITLE": True},
            ]
        )
        matcher_patterns.append(
            [
                {"LOWER": "he", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "who", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "must", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "not", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "be", "IS_TITLE": True},
                {"LOWER": "-"},
                {"LOWER": "named", "IS_TITLE": True},
            ]
        )
    return matcher_patterns
