from typing import Dict, List, Optional

Change = Dict[str, str]

def parse_section_header(line: str) -> Optional[str]:
    """
    If `line` starts with a section number like "1", "2.3", "10.11.5", followed
    by whitespace or end-of-line, return that number string. Otherwise return None.
    """
    i = 0
    n = len(line)

    # First, we need at least one digit
    if i < n and line[i].isdigit():
        # collect the first run of digits
        start = i
        while i < n and line[i].isdigit():
            i += 1

        # then zero or more groups of ".<digits>"
        while i < n and line[i] == '.':
            i += 1
            # require at least one digit after the dot
            if i < n and line[i].isdigit():
                while i < n and line[i].isdigit():
                    i += 1
            else:
                # malformed (e.g. ends with a dot): cancel
                return None

        # ensure next char is whitespace or end-of-line
        if i == n or line[i].isspace():
            return line[start:i]
    return None


def split_into_section_map(text: str) -> Dict[str, str]:
    """
    Parse `text` into a dict mapping section-number → full text block.
    A section starts on a line where parse_section_header() returns non‐None.
    Everything up to (but not including) the next such header belongs to that section.
    """
    lines = text.splitlines(keepends=True)
    section_map: Dict[str, List[str]] = {}
    current_sec: Optional[str] = None
    buffer: List[str] = []

    def flush():
        nonlocal buffer, current_sec
        if current_sec is not None:
            # join and strip trailing newlines
            section_map[current_sec] = ''.join(buffer).rstrip('\n')
        buffer = []

    for line in lines:
        sec = parse_section_header(line)
        if sec is not None:
            # new section detected
            flush()
            current_sec = sec
            buffer = [line]
        else:
            # continuation of current section block
            if current_sec is not None:
                buffer.append(line)
            # else: ignore any preamble before first section
    flush()
    return section_map


def section_key(s: str) -> tuple:
    """
    Turn "1.2.11" → (1,2,11) so tuple-sorting respects numeric hierarchy.
    """
    return tuple(int(part) for part in s.split('.'))


def detect_paragraph_section_changes(
    old_text: str,
    new_text: str
) -> List[Change]:
    """
    Diff two texts at the section level using our custom header parser.
    Returns a sorted list of change records:
      {section, change_type, old, new}
    in the order of numeric sections (1.*, then 2.*, etc.).
    """
    old_map = split_into_section_map(old_text)
    new_map = split_into_section_map(new_text)

    old_keys = set(old_map)
    new_keys = set(new_map)
    all_keys = sorted(old_keys | new_keys, key=section_key)

    changes: List[Change] = []

    for sec in all_keys:
        in_old = sec in old_keys
        in_new = sec in new_keys

        if in_old and not in_new:
            changes.append({
                "section": sec,
                "change_type": "Removed",
                "old": old_map[sec],
                "new": ""
            })
        elif not in_old and in_new:
            changes.append({
                "section": sec,
                "change_type": "Added",
                "old": "",
                "new": new_map[sec]
            })
        else:
            old_block = old_map[sec]
            new_block = new_map[sec]
            if old_block != new_block:
                changes.append({
                    "section": sec,
                    "change_type": "Modified",
                    "old": old_block,
                    "new": new_block
                })
            # identical → no record

    return changes


# --- Quick sanity test ---
if __name__ == "__main__":
    old = """
1.1 Introduction
This is the first section.

1.2 Details
Some details here.

2.1 Next Section
More text.
"""
    new = """
1.1 Introduction
This is the first section, with edits.

1.3 New Part
Brand new content.

1.2 Details
Some details here.

2.1 Next Section
More text.
"""
    for c in detect_paragraph_section_changes(old, new):
        print(f"{c['change_type']} {c['section']}")
        print("OLD:", repr(c['old']))
        print("NEW:", repr(c['new']))
        print("---")
