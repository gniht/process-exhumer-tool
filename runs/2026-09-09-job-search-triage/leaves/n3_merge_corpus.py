"""Leaf n3 - merge_corpus."""


def merge_corpus(corpus, new_postings):
    entries = []
    seen = set()

    for entry in (corpus or {}).get("entries") or []:
        key = (entry["source_id"], entry["source_posting_id"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)

    for posting in new_postings or []:
        key = (posting["source_id"], posting["source_posting_id"])
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "source_id": posting["source_id"],
                "source_posting_id": posting["source_posting_id"],
                "published_at": posting.get("published_at"),
                "raw_payload": posting["raw_payload"],
                "fields": {},
                "dispositions": {"viewed": False, "suppressed": False},
            }
        )

    corpus_with_new = dict(corpus or {})
    corpus_with_new["entries"] = entries
    return corpus_with_new
