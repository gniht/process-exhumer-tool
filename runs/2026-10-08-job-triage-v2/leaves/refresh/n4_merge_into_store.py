def merge_into_store(stored_postings, extracted_results, as_of):
    store = {(entry["source_id"], entry["posting_id"]): entry for entry in stored_postings}
    source_report = []

    for result in extracted_results:
        source_id = result["source_id"]
        if result["status"] != "ok":
            source_report.append({"source_id": source_id, "status": "failed", "reason": result["reason"]})
            continue

        listed_ids = set()
        new = listed_again = 0
        for posting in result["postings"]:
            key = (source_id, posting["posting_id"])
            listed_ids.add(posting["posting_id"])
            previous = store.get(key)
            if previous is None:
                new += 1
                first_seen = as_of
            else:
                first_seen = previous["first_seen"]
                if previous["listing"]["status"] == "no_longer_listed":
                    listed_again += 1
            store[key] = {
                "source_id": source_id,
                "posting_id": posting["posting_id"],
                "first_seen": first_seen,
                "listing": {"status": "listed", "since": None},
                "payload": posting["payload"],
                "fields": posting["fields"],
            }

        missed = [
            key for key, entry in store.items()
            if key[0] == source_id and key[1] not in listed_ids and entry["listing"]["status"] == "listed"
        ]
        for key in missed:
            store[key] = {**store[key], "listing": {"status": "no_longer_listed", "since": as_of}}

        source_report.append({
            "source_id": source_id,
            "status": "ok",
            "listed": len(result["postings"]),
            "new": new,
            "no_longer_listed": len(missed),
            "listed_again": listed_again,
        })

    return {
        "updated_postings": [store[key] for key in sorted(store)],
        "source_report": source_report,
    }
