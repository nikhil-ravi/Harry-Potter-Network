import random
import sys
from collections import Counter
from dataclasses import dataclass

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc

from .language import get_matcher_patterns
from .scraper import Character


@dataclass
class MatchResult:
    """Class representing a single match result from the matcher. Contains the string id, start and end character and the span of the match."""

    string_id: list[str]
    start: int
    end: int
    span: str

    def add_string_id(self, string_id: str) -> None:
        """Add a string id to the list of string ids.

        Args:
            string_id (str): String id to add
        """
        self.string_id.append(string_id)


hardcoded_options = dict()
# hardcoded_options["Malfoy"] = ["Draco Malfoy"]
hardcoded_options["Patil"] = ["Padma Patil", "Parvati Patil"]
hardcoded_options["Tom"] = ["Tom"]


def handle_multiple_options(results: list[MatchResult], doc: Doc) -> list[MatchResult]:
    """Handle multiple options for a single entity. This is done by finding the nearest entity and using that one.

    Args:
        results (list[MatchResult]): List of matched results
        doc (Doc): Spacy doc object in which the matches were found

    Returns:
        list[MatchResult]: List of matched results with disambiguated entities
    """
    needs_deduplication = [
        (i, result) for i, result in enumerate(results) if len(result.string_id) > 1
    ]
    for index, multiple_options in needs_deduplication:
        # Special logic for Dursleys, if there if Mr. then Vernon, if Mrs. then Petunia
        prefix = doc[multiple_options.start - 3 : multiple_options.start]
        if (multiple_options.span == "Dursley") and (
            ("Mr. and Mrs." in prefix.text) or ("Mrs. and Mr." in prefix.text)
        ):
            resolution = ["Vernon Dursley", "Petunia Dursley"]
        elif (multiple_options.span == "Dursley") and ("Mrs." in prefix.text):
            resolution = ["Petunia Dursley"]
        elif (multiple_options.span == "Dursley") and ("Mr." in prefix.text):
            resolution = ["Vernon Dursley"]
        elif (multiple_options.span == "Weasley") and ("Mrs." in prefix.text):
            resolution = ["Molly Weasley"]
        # Find nearest entity
        else:
            end_char = multiple_options.end
            distance = sys.maxsize
            resolution = []
            for possible_option in results:
                # Skip multiple options and entities that don't have any of the multiple option
                if (not len(possible_option.string_id) == 1) or (
                    not possible_option.string_id[0] in multiple_options.string_id
                ):
                    continue
                new_distance = abs(multiple_options.end - possible_option.end)
                if new_distance < distance:
                    distance = new_distance
                    resolution = possible_option.string_id

            if not resolution:
                try:
                    ho = hardcoded_options[multiple_options.span]
                    if len(ho) == 1:
                        resolution = ho
                    else:
                        resolution = [random.choice(ho)]
                except:
                    print(
                        f"no way to disambiguate {multiple_options.span} from options: {multiple_options.string_id}"
                    )

        results[index].string_id = resolution
    return results


def get_matcher(nlp: Language, chapter_characters: list[Character]) -> Matcher:
    """Get matcher object for the given characters.

    Args:
        nlp (Language): Spacy NLP object
        chapter_characters (list[Character]): List of characters to get matcher for

    Returns:
        Matcher: Spacy matcher object
    """
    matcher = Matcher(nlp.vocab)

    # Prepare character matcher
    for character in chapter_characters:
        matcher_pattern = get_matcher_patterns(character)
        matcher.add(character.title, matcher_pattern)

    return matcher


def coref_resolve_and_get_characters_matches_in_chapter(
    base_nlp: Language,
    nlp: Language,
    chapter_text: str,
    chapter_characters: list[Character],
    coref_resolver: callable,
) -> tuple[list[MatchResult], Doc]:
    """Resolve coreferences and get matches for the given characters in the chapter.

    Args:
        base_nlp (Language): The base nlp object without the coref and span_resolver components
        nlp (Language): The nlp object with the coref and span_resolver components
        chapter_text (str): The text of the chapter
        chapter_characters (list[Character]): The characters to find
        coref_resolver (callable): The coreference resolver

    Returns:
        tuple[list[MatchResult], Doc]: The list of match results and the resolved doc
    """
    matcher = get_matcher(nlp, chapter_characters)

    # Prepare text
    lines = chapter_text.split("\n")[1:]
    lines = list(filter(None, lines))
    chapter_title = lines[0]
    print(chapter_title)

    text = " ".join(lines[1:])
    base_doc = base_nlp(text)
    resolved_doc = list()
    for i in range(0, len(base_doc), 2000):
        tmp = coref_resolver(base_doc[i : i + 2000].text)
        resolved_doc.append(tmp)
    resolved_doc = Doc.from_docs(resolved_doc)
    # resolved_doc = coref_resolver(text)

    matches = matcher(resolved_doc)
    match_results: list[MatchResult] = []
    for match_id, start, end in matches:
        string_id = nlp.vocab.strings[match_id]
        span = resolved_doc[start:end]

        exists_long = [
            (start == res.start and end < res.end)
            or (start > res.start and end == res.end)
            for res in match_results
        ]
        same = [start == res.start and end == res.end for res in match_results]
        shorter_end = [
            (start == res.start and end > res.start) and end < res.end
            for res in match_results
        ]
        shorter_start = [
            (start < res.start and end == res.start) and end < res.end
            for res in match_results
        ]

        if any(exists_long):
            continue

        if any(shorter_end):
            del match_results[shorter_end.index(True)]
            match_results.append(
                MatchResult(
                    string_id=[string_id],
                    start=start,
                    end=end,
                    span=span.text,
                )
            )
        elif any(shorter_start):
            del match_results[shorter_start.index(True)]
            match_results.append(
                MatchResult(
                    string_id=[string_id],
                    start=start,
                    end=end,
                    span=span.text,
                )
            )
        elif not any(same):
            match_results.append(
                MatchResult(
                    string_id=[string_id],
                    start=start,
                    end=end,
                    span=span.text,
                )
            )
        else:
            i = same.index(True)
            match_results[i].add_string_id(string_id)

    handle_multiple_options(match_results, resolved_doc)
    return match_results, resolved_doc


def flatten_results(results: list[MatchResult]) -> list[MatchResult]:
    """Flatten the results to have a single string id per result.

    Args:
        results (list[MatchResult]): List of match results

    Returns:
        list[MatchResult]: List of match results with a single string id per result
    """
    flat_results = []
    for res in results:
        if len(res.string_id) == 1:
            flat_results.append(res)
        else:
            for string_id in res.string_id:
                flat_results.append(
                    MatchResult(
                        string_id=[string_id],
                        start=res.start,
                        end=res.end,
                        span=res.span,
                    )
                )
    return flat_results


def get_interactions(
    results: list[MatchResult], distance_threshold: int = 14
) -> Counter:
    """Get interactions from the given results.

    Args:
        results (list[MatchResult]): List of match results
        distance_threshold (int, optional): The distance between two Entities for them to be considered an interaction. Defaults to 14.

    Returns:
        Counter: Counter of interactions
    """
    # sort by start character
    results = sorted(results, key=lambda k: k.start)
    compact_entities = []
    # Merge entities
    for entity in results:
        # If the same entity occurs, prolong the end
        if (len(compact_entities) > 0) and (
            compact_entities[-1].string_id == entity.string_id
        ):
            compact_entities[-1].end = entity.end
        else:
            compact_entities.append(entity)
    interactions = list()
    # Iterate over all entities
    for index, source in enumerate(compact_entities[:-1]):
        # Compare with entities that come after the given one
        for target in compact_entities[index + 1 :]:
            if (source.string_id != target.string_id) and (
                abs(source.end - target.start) < distance_threshold
            ):
                link = sorted([source.string_id[0], target.string_id[0]])
                interactions.append(link)
            else:
                break
    # Count the number of interactions
    return Counter(map(tuple, interactions))