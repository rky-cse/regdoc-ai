import difflib

def extract_changes(text_v1: str, text_v2: str):
    # … split into paras_v1, paras_v2 …
    paras_v1 = [p for p in text_v1.split("\n\n") if p.strip()]
    paras_v2 = [p for p in text_v2.split("\n\n") if p.strip()]

    changes = []
    matcher = difflib.SequenceMatcher(None, paras_v1, paras_v2)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        elif tag == "replace":
            len_old, len_new = i2 - i1, j2 - j1
            min_len = min(len_old, len_new)
            # pairwise modifications
            for k in range(min_len):
                old_p = paras_v1[i1 + k].strip()
                new_p = paras_v2[j1 + k].strip()
                if old_p != new_p:
                    changes.append({"category": "modified", "text": new_p})
            # extras
            if len_new > len_old:
                for p in paras_v2[j1 + min_len : j2]:
                    changes.append({"category": "added",    "text": p})
            elif len_old > len_new:
                for p in paras_v1[i1 + min_len : i2]:
                    changes.append({"category": "deleted",  "text": p})

        elif tag == "delete":
            for p in paras_v1[i1:i2]:
                changes.append({"category": "deleted", "text": p})

        elif tag == "insert":
            for p in paras_v2[j1:j2]:
                changes.append({"category": "added",   "text": p})

    # ── fallback for single‐line or no‐opcode diffs ──
    if not changes and text_v1.strip() != text_v2.strip():
        changes.append({"category": "modified", "text": text_v2.strip()})

    return changes