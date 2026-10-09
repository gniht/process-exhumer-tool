import datetime
import re

_PARENT = {
    "north_america": "americas", "latin_america": "americas",
    "europe": "emea", "middle_east": "emea", "africa": "emea",
    "asia": "apac", "oceania": "apac",
}
_SINGLE_VALUED = {"company", "work_arrangement", "employment_type", "listing_status"}
_ALTERNATIVES = {"countries", "regions", "seniority"}


def _containing(region):
    """The region and every region containing it."""
    chain = [region]
    while chain[-1] in _PARENT:
        chain.append(_PARENT[chain[-1]])
    return chain


def _norm(value):
    return value.strip().casefold() if isinstance(value, str) else value


def _keyword_pattern(keyword):
    keyword = keyword.strip()
    continues = keyword.endswith("*")
    if continues:
        keyword = keyword[:-1].rstrip()
    words = keyword.split()
    if not words:
        return None
    body = r"\s+".join(re.escape(word) for word in words)
    tail = r"[^\W_]*" if continues else ""
    return re.compile(r"(?<![^\W_])" + body + tail + r"(?![^\W_])", re.IGNORECASE)


def _tested(posting, field):
    """The field's value and the evidence it carries."""
    if field == "first_seen":
        value = posting["first_seen"]
        return value, [{"path": "entry.first_seen", "span": None, "raw": value, "value": value}]
    if field == "listing_status":
        listing = posting["listing"]
        return listing["status"], [{"path": "entry.listing", "span": None, "raw": listing, "value": listing["status"]}]
    record = (posting.get("fields") or {}).get(field) or {}
    return record.get("value"), list(record.get("evidence") or [])


def _over_alternatives(outcomes, action):
    """Combine per-value outcomes ('meets', 'fails', 'unknown') into a verdict for the action."""
    if action == "exclude":
        if all(outcome == "meets" for outcome in outcomes):
            return "met"
        if any(outcome == "fails" for outcome in outcomes):
            return "not_met"
        return "cant_tell"
    if any(outcome == "meets" for outcome in outcomes):
        return "met"
    if any(outcome == "unknown" for outcome in outcomes):
        return "cant_tell"
    return "not_met"


def _region_outcome(region, wanted):
    if any(r in wanted for r in _containing(region)):
        return "meets"
    if any(region in _containing(w)[1:] for w in wanted):
        return "unknown"  # a rule value lies strictly inside this region
    return "fails"


def _contains(rule, value, evidence):
    patterns = [(k, p) for k, p in ((k, _keyword_pattern(k)) for k in rule["keywords"]) if p]
    texts = [(e["path"], e["value"]) for e in evidence if isinstance(e.get("value"), str)]
    if rule["field"] == "title":
        texts = [t for t in texts if t[1] == value][:1] or [("title", value)]
    matches = []
    for path, text in texts:
        for keyword, pattern in patterns:
            for match in pattern.finditer(text):
                matches.append({"path": path, "span": [match.start(), match.end()],
                                "raw": match.group(0), "value": keyword})
    return ("met", matches) if matches else ("not_met", evidence)


def _compare(test, amount, number):
    return number >= amount if test == "at_least" else number <= amount


def evaluate_rule(posting, rule, as_of):
    field, test, action = rule["field"], rule["test"], rule["action"]
    value, evidence = _tested(posting, field)

    def verdict(result, rested_on=None):
        return {"rule_id": rule["id"], "result": result, "field": field, "value": value,
                "evidence": evidence if rested_on is None else rested_on}

    if value is None:
        return verdict("cant_tell")

    if test == "contains":
        result, rested_on = _contains(rule, value, evidence)
        return verdict(result, rested_on)

    if test == "one_of":
        wanted = [_norm(v) for v in rule["values"]]
        if field in _SINGLE_VALUED:
            return verdict("met" if _norm(value) in wanted else "not_met")
        if field == "department_team":
            return verdict("met" if any(_norm(v) in wanted for v in value) else "not_met")
        if field == "regions":
            outcomes = [_region_outcome(region, wanted) for region in value]
        elif field in _ALTERNATIVES:
            outcomes = ["meets" if _norm(v) in wanted else "fails" for v in value]
        else:
            raise ValueError(f"one_of does not apply to {field!r}")
        return verdict(_over_alternatives(outcomes, action))

    if test in ("at_least", "at_most"):
        amount = rule["amount"]
        if field == "years_of_experience":
            return verdict("met" if _compare(test, amount, value) else "not_met")
        if field == "salary":
            currency, period = value.get("currency"), value.get("pay_period")
            if currency is None or period is None:
                return verdict("cant_tell")
            if _norm(currency) != _norm(rule["currency"]) or _norm(period) != _norm(rule["pay_period"]):
                return verdict("cant_tell")
            # Every amount from minimum to maximum is an alternative; the endpoints decide.
            outcomes = ["meets" if _compare(test, amount, v) else "fails"
                        for v in (value["minimum"], value["maximum"])]
            return verdict(_over_alternatives(outcomes, action))
        raise ValueError(f"{test} does not apply to {field!r}")

    if test == "within_days":
        earliest = datetime.date.fromisoformat(as_of) - datetime.timedelta(days=rule["days"])
        return verdict("met" if datetime.date.fromisoformat(value) >= earliest else "not_met")

    raise ValueError(f"unknown test {test!r}")
