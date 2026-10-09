def diagnose_rules(rules, verdicts, hidden):
    rule_diagnostics = []
    for rule in rules:
        rule_id = rule["id"]
        counts = {"met": 0, "not_met": 0, "cant_tell": 0}
        could_not_check = []
        for item in verdicts:
            for verdict in item["verdicts"]:
                if verdict["rule_id"] != rule_id:
                    continue
                counts[verdict["result"]] += 1
                if verdict["result"] == "cant_tell":
                    could_not_check.append({"source_id": item["source_id"], "posting_id": item["posting_id"]})

        hid = hid_couldnt_check = 0
        for record in hidden:
            kinds = {reason["kind"] for reason in record["reasons"] if reason.get("rule_id") == rule_id}
            if kinds:
                hid += 1
                if "couldnt_check" in kinds:
                    hid_couldnt_check += 1

        could_not_check.sort(key=lambda key: (key["source_id"], key["posting_id"]))
        rule_diagnostics.append({
            "rule_id": rule_id,
            **counts,
            "hid": hid,
            "hid_couldnt_check": hid_couldnt_check,
            "could_not_check": could_not_check,
        })
    return rule_diagnostics
