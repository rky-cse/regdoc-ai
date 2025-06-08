import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple

SectionName = str
Paragraph = str
Change = Dict[str, List[Tuple[int, Paragraph]]]

def split_into_sections(text: str) -> Dict[SectionName, List[Paragraph]]:
    """
    Split text into sections based on headings like '1.', '1.2', '2.3.4', etc.,
    then split each section into paragraphs (blocks separated by blank lines).
    Returns a dict: { section_heading: [paragraph1, paragraph2, ...], ... }
    """
    # Normalize line endings and strip trailing spaces
    lines = [line.rstrip() for line in text.strip().splitlines()]
    section_re = re.compile(r'^(\d+(?:\.\d+)*)(?:\s+|$)')  # captures "1", "1.2.3", etc.

    sections: Dict[SectionName, List[str]] = {}
    current_sec = '0'  # default “no-number” section
    buffer: List[str] = []

    def flush_buffer():
        para = '\n'.join(buffer).strip()
        if para:
            sections.setdefault(current_sec, []).append(para)
        buffer.clear()

    for line in lines:
        m = section_re.match(line)
        if m:
            # new section begins
            flush_buffer()
            current_sec = m.group(1)
            sections.setdefault(current_sec, [])
            # remainder of line becomes first paragraph line
            rest = line[m.end():].strip()
            if rest:
                buffer.append(rest)
        else:
            if line.strip() == '':
                # blank line: paragraph boundary
                flush_buffer()
            else:
                buffer.append(line)
    flush_buffer()
    return sections

def diff_paragraphs(old_paras: List[Paragraph], new_paras: List[Paragraph]) -> Change:
    """
    Compare two lists of paragraphs and return dict with keys 'added', 'removed', 'changed'.
    Each value is a list of (index, paragraph) tuples.
    """
    sm = SequenceMatcher(a=old_paras, b=new_paras, autojunk=False)
    changes: Change = {'added': [], 'removed': [], 'changed': []}

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'delete':
            for i in range(i1, i2):
                changes['removed'].append((i, old_paras[i]))
        elif tag == 'insert':
            for j in range(j1, j2):
                changes['added'].append((j, new_paras[j]))
        elif tag == 'replace':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                changes['changed'].append(((i, old_paras[i]), (j, new_paras[j])))
            # handle mismatched counts
            if (i2 - i1) < (j2 - j1):
                for j in range(j1 + (i2 - i1), j2):
                    changes['added'].append((j, new_paras[j]))
            elif (i2 - i1) > (j2 - j1):
                for i in range(i1 + (j2 - j1), i2):
                    changes['removed'].append((i, old_paras[i]))
    return changes

def detect_paragraph_section_changes(old_text: str, new_text: str) -> Dict[SectionName, Change]:
    """
    Top-level function. Returns a dict mapping each section to its Change dict.
    Sections present in one version only show all paras as added/removed.
    """
    old_secs = split_into_sections(old_text)
    new_secs = split_into_sections(new_text)
    all_sections = set(old_secs) | set(new_secs)

    result: Dict[SectionName, Change] = {}
    for sec in sorted(all_sections, key=lambda s: list(map(int, s.split('.')))):
        old_paras = old_secs.get(sec, [])
        new_paras = new_secs.get(sec, [])
        result[sec] = diff_paragraphs(old_paras, new_paras)
    return result

# --- Example usage / test ---
if __name__ == '__main__':
    old = """
1. Introduction

This is the first paragraph.
This is still part of the first paragraph.

This is the second paragraph.

2. Methods

Here is a method description.
"""

    new = """
1. Introduction

This is the first paragraph, with an edit.
This is still part of the first paragraph.

This is the second paragraph.

2. Methods

Here is a method description.

An added third paragraph in methods.

3. Conclusion

A completely new section.
"""
    changes = detect_paragraph_section_changes(old, new)
    for sec, diff in changes.items():
        print(f"Section {sec}:")
        for typ in ('removed', 'added'):
            for idx, para in diff[typ]:
                print(f"  {typ.upper()} at idx {idx}:")
                print(f"    {para!r}")
        for ((i, o), (j, n)) in diff['changed']:
            print(f"  CHANGED old idx {i} -> new idx {j}:")
            print(f"    - {o!r}")
            print(f"    + {n!r}")
        print()
