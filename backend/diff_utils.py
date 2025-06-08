import re
from typing import Dict, List

Change = Dict[str, str]

def split_into_section_map(text: str) -> Dict[str, str]:
    """
    Parse the document into a map: section_number -> full section text.
    A section starts on a line matching ^(\d+(?:\.\d+)*)\b and includes
    all following lines up to (but not including) the next such header.
    """
    # Normalize line endings
    lines = text.splitlines(keepends=True)
    section_re = re.compile(r'^(\d+(?:\.\d+)*)\b')

    section_map: Dict[str, List[str]] = {}
    current_sec: str = None
    buffer: List[str] = []

    def flush_section():
        nonlocal current_sec, buffer
        if current_sec is not None:
            # Join everything we’ve buffered for this section
            section_map[current_sec] = ''.join(buffer).rstrip()
        buffer = []

    for line in lines:
        m = section_re.match(line)
        if m:
            # Found a new section header
            # First flush the previous one
            flush_section()
            # Start a new buffer, include this header line
            current_sec = m.group(1)
            buffer = [line]
        else:
            # Continuation of current section (or preamble if no section yet)
            if current_sec is None:
                # Skip any lines before the first numbered section
                continue
            buffer.append(line)

    # Flush the last section
    flush_section()
    return section_map


def detect_paragraph_section_changes(
    old_text: str,
    new_text: str
) -> List[Change]:
    """
    Compare two documents at the section level and return a flat list of changes.
    """
    old_map = split_into_section_map(old_text)
    new_map = split_into_section_map(new_text)

    old_keys = set(old_map)
    new_keys = set(new_map)

    changes: List[Change] = []

    # Added sections
    for sec in sorted(new_keys - old_keys, key=lambda s: list(map(int, s.split('.')))):
        changes.append({
            "section": sec,
            "change_type": "Added",
            "old": "",
            "new": new_map[sec]
        })

    # Removed sections
    for sec in sorted(old_keys - new_keys, key=lambda s: list(map(int, s.split('.')))):
        changes.append({
            "section": sec,
            "change_type": "Removed",
            "old": old_map[sec],
            "new": ""
        })

    # Modified sections
    for sec in sorted(old_keys & new_keys, key=lambda s: list(map(int, s.split('.')))):
        if old_map[sec] != new_map[sec]:
            changes.append({
                "section": sec,
                "change_type": "Modified",
                "old": old_map[sec],
                "new": new_map[sec]
            })

    return changes


# --- quick sanity test ---
if __name__ == "__main__":
    old = """
1. Intro
This is paragraph one.

Still in section 1.

2. Details
Detail line A.
Detail line B.

3. Conclusion
Done.
"""
    new = """
1. Intro
This is paragraph one, edited.

Still in section 1.

2. Details
Detail line A.
Detail line B.
New extra detail.

4. Appendix
Some extra stuff.
"""
    for change in detect_paragraph_section_changes(old, new):
        print(f"{change['change_type']} section {change['section']}")
        print("OLD:")
        print(change['old'])
        print("---")
        print("NEW:")
        print(change['new'])
        print("========\n")
