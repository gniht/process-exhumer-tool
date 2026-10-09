import re

_ISO_4217 = set(
    "AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN "
    "BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS "
    "GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW "
    "KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD "
    "NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD "
    "SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VES "
    "VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWL".split()
)
# Symbols that name one currency; a bare '$' is handled separately.
_SYMBOLS = {
    "US$": "USD", "CA$": "CAD", "CAD$": "CAD", "C$": "CAD", "AU$": "AUD", "A$": "AUD",
    "NZ$": "NZD", "S$": "SGD", "HK$": "HKD", "MX$": "MXN", "R$": "BRL", "€": "EUR", "£": "GBP",
}
_CODE = r"(?<![A-Za-z])(?:" + "|".join(sorted(_ISO_4217)) + r")(?![A-Za-z])"
_SYMBOL = "(?:" + "|".join(re.escape(s) for s in sorted(_SYMBOLS, key=len, reverse=True)) + r"|\$)"
_FIGURE = r"\d{1,3}(?:[,.  ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_RANGE = re.compile(
    rf"(?:(?P<pre>{_CODE}|{_SYMBOL})\s?)?(?<![\d.,])(?P<a>{_FIGURE})(?:\s?(?P<ak>[kK])(?![A-Za-z]))?"
    rf"(?:\s?(?P<mid>{_CODE}))?"
    r"\s*(?:-|–|—|to)\s*"
    rf"(?:(?P<pre2>{_CODE}|{_SYMBOL})\s?)?(?P<b>{_FIGURE})(?![\d])(?:\s?(?P<bk>[kK])(?![A-Za-z]))?"
    rf"(?:\s?(?P<post>{_CODE}))?"
)
_PERIODS = [
    ("hour", re.compile(r"\bper\s+hour\b|/\s*h(?:ou)?r\b|\bhourly\b", re.IGNORECASE)),
    ("day", re.compile(r"\bper\s+day\b|/\s*day\b|\bdaily\b", re.IGNORECASE)),
    ("week", re.compile(r"\bper\s+week\b|/\s*w(?:ee)?k\b|\bweekly\b", re.IGNORECASE)),
    ("month", re.compile(r"\bper\s+month\b|/\s*mo(?:nth)?\b|\bmonthly\b", re.IGNORECASE)),
    ("year", re.compile(
        r"\bper\s+year\b|/\s*y(?:ea)?r\b|\bannually\b|\bannual\b|\byearly\b|\bper\s+annum\b", re.IGNORECASE
    )),
]
_WINDOW = 40


def _number(text):
    text = text.replace(" ", "").replace(" ", "")
    decimal = re.search(r"[.,](\d{1,2})$", text)
    whole = text[: decimal.start()] if decimal else text
    whole = re.sub(r"[.,]", "", whole)
    value = float(f"{whole}.{decimal.group(1)}") if decimal else float(whole)
    return int(value) if value.is_integer() else value


def _currency(match, countries):
    explicit = set()
    bare_dollar = False
    for group in ("pre", "mid", "pre2", "post"):
        token = match.group(group)
        if not token:
            continue
        if token in _ISO_4217:
            explicit.add(token)
        elif token in _SYMBOLS:
            explicit.add(_SYMBOLS[token])
        else:
            bare_dollar = True
    if len(explicit) > 1:
        return False, None  # the statement names two currencies: not a recognisable salary
    if explicit:
        return True, explicit.pop()
    if bare_dollar:
        return True, "USD" if countries == ["US"] else None
    return False, None


def _stated_periods(text, spans):
    """For each statement span, (stated, period): the periods named beside it, within the window on the
    same line, and nearer to it than to any other statement in the text."""
    hits = [(period, match.start(), match.end()) for period, pattern in _PERIODS for match in pattern.finditer(text)]

    def distance(span, start, end):
        if end <= span[0]:
            gap, between = span[0] - end, text[end:span[0]]
        elif start >= span[1]:
            gap, between = start - span[1], text[span[1]:start]
        else:
            return None
        return gap if gap + (end - start) <= _WINDOW and "\n" not in between else None

    results = []
    for span in spans:
        named = set()
        for period, start, end in hits:
            mine = distance(span, start, end)
            if mine is None:
                continue
            others = [d for d in (distance(other, start, end) for other in spans if other != span) if d is not None]
            if all(mine <= d for d in others):
                named.add(period)
        results.append((True, named.pop()) if len(named) == 1 else (bool(named), None))
    return results


def derive_salary(full_text, countries, pay_floors):
    country_codes = (countries or {}).get("value")
    statements = []
    for entry in (full_text or {}).get("evidence") or []:
        text = entry.get("value")
        if not isinstance(text, str):
            continue
        found = []
        for match in _RANGE.finditer(text):
            recognised, currency = _currency(match, country_codes)
            if not recognised:
                continue
            low, high = _number(match.group("a")), _number(match.group("b"))
            if match.group("ak"):
                low *= 1000
            if match.group("bk"):
                high *= 1000
                if not match.group("ak") and low < 1000:
                    low *= 1000
            if 0 < low <= high:
                found.append((match, currency, low, high))
        periods = _stated_periods(text, [match.span() for match, *_ in found])
        for (match, currency, low, high), (stated, period) in zip(found, periods):
            if not stated and currency is not None and currency in (pay_floors or {}):
                if low >= pay_floors[currency]:
                    period = "year"
            salary = {"minimum": low, "maximum": high, "currency": currency, "pay_period": period}
            statements.append({"path": entry["path"], "span": list(match.span()),
                               "raw": match.group(0), "value": salary})

    if not statements:
        return {"value": None, "evidence": []}
    kinds = {(s["value"]["currency"], s["value"]["pay_period"]) for s in statements}
    if len(kinds) > 1:
        return {"value": None, "evidence": statements}
    currency, period = kinds.pop()
    value = {
        "minimum": min(s["value"]["minimum"] for s in statements),
        "maximum": max(s["value"]["maximum"] for s in statements),
        "currency": currency,
        "pay_period": period,
    }
    return {"value": value, "evidence": statements}
