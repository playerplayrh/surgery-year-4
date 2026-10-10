"""Small helpers shared by validate.py and build_facts.py. Standard library only."""
import math
import re

FM_RE = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
TAG_RE = re.compile(r"\[(L\s*\d+(?:\s*(?:-|–|,)\s*L?\s*\d+)*)\]")
THAI_RE = re.compile(r"[฀-๿]")


def read_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _strip_comment(value):
    quote = None
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1] in " \t"):
            return value[:i]
    return value


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_list(inner):
    items, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    items.append(buf)
    return [_unquote(i) for i in items if i.strip()]


def parse_front_matter(block):
    """Flat `key: value`, `key: [a, b]`, and `key:` followed by `- item` lines."""
    data, key = {}, None
    for raw in block.split("\n"):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):(.*)$", raw)
        if m and not raw.startswith((" ", "\t")):
            key = m.group(1)
            val = _strip_comment(m.group(2)).strip()
            if val.startswith("[") and val.endswith("]"):
                data[key] = _split_list(val[1:-1])
            else:
                data[key] = _unquote(val)
        elif key and raw.strip().startswith("- "):
            if not isinstance(data[key], list):
                data[key] = [] if data[key] == "" else [data[key]]
            data[key].append(_unquote(_strip_comment(raw.strip()[2:])))
    return data


def split_front_matter(text):
    """Return (front-matter dict or None, body, number of lines taken by the front-matter)."""
    m = FM_RE.match(text)
    if not m:
        return None, text, 0
    return parse_front_matter(m.group(1)), text[m.end():], text[:m.end()].count("\n")


def tag_lines(text):
    """Set of raw line numbers referenced by [L12], [L12-14], [L12, L15] tags."""
    found = set()
    for m in TAG_RE.finditer(text):
        for part in re.split(r"\s*,\s*", m.group(1)):
            nums = [int(n) for n in re.findall(r"\d+", part)]
            if ("-" in part or "–" in part) and len(nums) == 2:
                if nums[0] <= nums[1] <= nums[0] + 2000:
                    found.update(range(nums[0], nums[1] + 1))
            else:
                found.update(nums)
    return found


def norm(text):
    """Case-folded text with markdown and ASCII punctuation collapsed to single spaces."""
    return re.sub(r"[\s\-_/,.;:()\[\]{}*|`'\"#>]+", " ", text.casefold()).strip()


def count_words(text):
    """Whitespace words, plus about one word per 5 Thai characters (Thai has no spaces)."""
    thai = len(THAI_RE.findall(text))
    return len(THAI_RE.sub(" ", text).split()) + math.ceil(thai / 5)
