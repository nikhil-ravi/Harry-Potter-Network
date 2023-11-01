import random
import sys
from collections import Counter
from dataclasses import dataclass

from spacy.language import Language
from spacy.tokens import Doc

from .language import get_matcher
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
hardcoded_options["Malfoy"] = ["Draco Malfoy"]
hardcoded_options["Patil"] = ["Padma Patil", "Parvati Patil"]
hardcoded_options["Tom"] = ["Tom"]
hardcoded_options["Ravenclaw"] = ["Rowena Ravenclaw"]
hardcoded_options["Hufflepuff"] = ["Helga Hufflepuff"]
hardcoded_options["Slytherin"] = ["Salazar Slytherin"]
hardcoded_options["Gryffindor"] = ["Godric Gryffindor"]
hardcoded_options["Riddle"] = ["Tom Riddle"]
# Book 3
hardcoded_options["Lily"] = ["Lily J. Potter"]
hardcoded_options["Lupin"] = ["Remus Lupin"]
# Book 4
hardcoded_options["Bagman"] = ["Ludovic Bagman"]
hardcoded_options["Dennis"] = ["Dennis Creevey"]
hardcoded_options["Crouch"] = ["Bartemius Crouch Senior"]
hardcoded_options["Barty"] = ["Bartemius Crouch Senior"]
hardcoded_options["Bartemius"] = ["Bartemius Crouch Senior"]
hardcoded_options["Longbottom"] = ["Neville Longbottom"]
hardcoded_options["Dumbledore"] = ["Albus Dumbledore"]
hardcoded_options["Crabbe"] = ["Vincent Crabbe"]
hardcoded_options["Goyle"] = ["Gregory Goyle"]
hardcoded_options["Nott"] = ["Theodore Nott"]
# Book 5
hardcoded_options["Malcolm"] = ["Malcolm"]
hardcoded_options["Tonks"] = ["Nymphadora Tonks"]
hardcoded_options["Frank"] = ["Frank Longbottom"]
hardcoded_options["Diggory"] = ["Cedric Diggory"]
hardcoded_options["Trelawney"] = ["Sybill Trelawney"]
hardcoded_options["Lestrange"] = ["Bellatrix Lestrange"]
hardcoded_options["Snape"] = ["Severus Snape"]
hardcoded_options["Fortescue"] = ["Dexter Fortescue"]
hardcoded_options["Stebbins"] = ["Stebbins (Potter-era)"]
hardcoded_options["Avery"] = ["Avery (Marauder-era)"]
hardcoded_options["Mulciber"] = ["Mulciber (Marauder-era)"]
hardcoded_options["Delacour"] = ["Fleur Delacour"]
hardcoded_options["Cornelius"] = ["Cornelius Fudge"]


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
        suffix = doc[multiple_options.end : multiple_options.end + 3]
        if (multiple_options.span == "Dursley") and (
            ("Mr. and Mrs." in prefix.text) or ("Mrs. and Mr." in prefix.text)
        ):
            resolution = ["Vernon Dursley", "Petunia Dursley"]
        elif (multiple_options.span == "Dursley") and ("Mrs." in prefix.text):
            resolution = ["Petunia Dursley"]
        elif (multiple_options.span == "Dursley") and ("Mr." in prefix.text):
            resolution = ["Vernon Dursley"]
        elif (multiple_options.span == "Dursley") and ("ish" in suffix.text):
            resolution = ["Vernon Dursley", "Petunia Dursley", "Dudley Dursley"]
        elif (multiple_options.span == "Weasley") and (
            ("Mr. and Mrs." in prefix.text) or ("Mrs. and Mr." in prefix.text)
        ):
            resolution = ["Arthur Weasley", "Molly Weasley"]
        elif (multiple_options.span == "Weasley") and ("Mrs." in prefix.text):
            resolution = ["Molly Weasley"]
        elif (multiple_options.span == "Malfoy") and ("Mrs." in prefix.text):
            resolution = ["Narcissa Malfoy"]
        elif (multiple_options.span == "Malfoy") and ("Mr." in prefix.text):
            resolution = ["Lucius Malfoy"]
        elif (multiple_options.span == "Malfoy") and (
            not ("Mr." in prefix.text) or ("Mrs." in prefix.text)
        ):
            resolution = ["Draco Malfoy"]
        elif (multiple_options.span == "Diggory") and ("Mr." in prefix.text):
            resolution = ["Amos Diggory"]
        elif (multiple_options.span == "Creevey") and ("brothers" in suffix.text):
            resolution = ["Colin Creevey", "Dennis Creevey"]
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
                if multiple_options.span == "Senior":
                    continue
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


def coref_resolve_and_get_characters_matches_in_chapter(
    base_nlp: Language,
    nlp: Language,
    chapter_text: str,
    characters_seen_till_this_chapter: list[Character],
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
    matcher = get_matcher(nlp, characters_seen_till_this_chapter)

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
