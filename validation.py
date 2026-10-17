"""
Validation of the dictionary entry returned by the model.

The model's output is never trusted: it is parsed, checked against the required structure and
cleaned before the application uses it. Any problem raises ValidationError with a list of reasons.
"""

import json
import re

REQUIRED_FIELDS = ("word", "definitions", "synonyms", "antonyms", "examples")
LIST_FIELDS = ("definitions", "synonyms", "antonyms", "examples")
MAX_ITEMS = 10          # per list
MAX_ITEM_LENGTH = 300   # characters per list item


class ValidationError(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def extract_json(raw: str) -> dict:
    """Parse the model's text as a JSON object, tolerating ```json fences or text around the object."""
    if raw is None or not raw.strip():
        raise ValidationError(["the model returned an empty response"])
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValidationError(["the response is not JSON"])
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            raise ValidationError([f"the response is not valid JSON ({e.msg} at position {e.pos})"])
    if not isinstance(data, dict):
        raise ValidationError([f"the JSON must be an object, not {type(data).__name__}"])
    return data


def _normalise(s: str) -> str:
    return " ".join(s.split()).casefold()


def validate_entry(data: dict, requested_word: str) -> tuple[dict, list[str]]:
    """
    Check the structure and content of a dictionary entry.
    Returns (clean_entry, warnings). Raises ValidationError if the entry cannot be used.
    """
    problems, warnings = [], []

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        problems.append("missing field(s): " + ", ".join(missing))
    extra = [k for k in data if k not in REQUIRED_FIELDS]
    if extra:
        warnings.append("ignored unexpected field(s): " + ", ".join(map(str, extra)))

    # word
    word = data.get("word")
    if "word" in data:
        if not isinstance(word, str) or not word.strip():
            problems.append("'word' must be a non-empty string")
        elif _normalise(word) != _normalise(requested_word):
            problems.append(f"'word' is '{word}', but the requested word was '{requested_word}'")

    # lists
    clean = {"word": requested_word.strip()}
    for field in LIST_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if not isinstance(value, list):
            problems.append(f"'{field}' must be a list, not {type(value).__name__}")
            continue
        items, seen = [], set()
        for i, item in enumerate(value):
            if not isinstance(item, str):
                problems.append(f"'{field}'[{i}] must be a string, not {type(item).__name__}")
                continue
            item = " ".join(item.split())
            if not item:
                problems.append(f"'{field}'[{i}] is an empty string")
                continue
            if len(item) > MAX_ITEM_LENGTH:
                problems.append(f"'{field}'[{i}] is longer than {MAX_ITEM_LENGTH} characters")
                continue
            key = item.casefold()
            if key in seen:
                warnings.append(f"removed duplicate in '{field}': {item}")
                continue
            seen.add(key)
            items.append(item)
        if len(items) > MAX_ITEMS:
            warnings.append(f"'{field}' had {len(items)} items; kept the first {MAX_ITEMS}")
            items = items[:MAX_ITEMS]
        clean[field] = items

    # content rules
    if "definitions" in clean and not clean["definitions"]:
        problems.append("'definitions' is empty: at least one definition is required")

    target = _normalise(requested_word)
    for field in ("synonyms", "antonyms"):
        if field in clean and any(_normalise(x) == target for x in clean[field]):
            problems.append(f"'{field}' contains the word itself")
    if "synonyms" in clean and "antonyms" in clean:
        overlap = {x.casefold() for x in clean["synonyms"]} & {x.casefold() for x in clean["antonyms"]}
        if overlap:
            problems.append("the same word appears as both synonym and antonym: " + ", ".join(sorted(overlap)))

    if problems:
        raise ValidationError(problems)
    return {f: clean[f] for f in REQUIRED_FIELDS}, warnings


def validate_word_input(word: str) -> str:
    """Validate what the user typed before it is sent to the model."""
    word = " ".join(word.split())
    if not word:
        raise ValueError("please type a word")
    if len(word) > 50:
        raise ValueError("the word is too long (max 50 characters)")
    if not re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", word):
        raise ValueError("use letters only (single spaces, hyphens and apostrophes are allowed between letters)")
    return word
