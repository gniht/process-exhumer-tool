"""job_triage_refresh.py: assembled by process-exhumer stage 5 from a verified tree. No model is called, and there are no
decision points, so no decision runtime is included.

Usage: python3 job_triage_refresh.py < inputs.json > outputs.json

What this program is (the root contract's behavior):

Given source definitions, the stored postings, a pay-floor table and the current date: for every source whose fetch succeeds, every posting it lists is present in the returned store under its source and posting ID, a posting not previously stored being added with the current date as its first-seen date and one already stored being replaced by the version just fetched with its first-seen date kept; every stored posting has every declared field extracted from the payload it carries, each value either within that field's declared value space or unknown and carrying the board's raw value and its location in the payload, a board's value being mapped into a value space only by the source definition's value maps and date format, or by the program's fixed tables of names, words and forms, which decide: what they do not cover is unknown, and an entry counts wherever it appears; a salary is extracted only where the posting states it in a recognisable form, a bare $ being read as USD only where the US is the posting's only country, and a pay period the posting does not state being read as yearly only where the salary's currency has a pay-floor entry and the lower figure is at least that floor, and otherwise unknown; a stored posting from a successfully fetched source that the fetch did not list is marked no longer listed with the date it was first missed, and one so marked that is listed again has the mark cleared; a source whose fetch fails changes nothing stored from it and affects no other source; no stored posting is ever removed; and the report states for every source whether its fetch succeeded and, if it did, how many postings it listed, how many were new, how many were newly no longer listed and how many were listed again, or, if it did not, the reason.
"""


def fetch_source__n5(source):
    # --- leaf n5 code, verbatim ---
    import json
    import urllib.error
    import urllib.request

    _TIMEOUT_SECONDS = 30


    def _read_path(value, path):
        """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
        found = [("", value)]
        for part in path.split("."):
            step_in = part.endswith("[]")
            key = part[:-2] if step_in else part
            reached = []
            for prefix, current in found:
                if key:
                    if not isinstance(current, dict) or key not in current:
                        continue
                    current = current[key]
                    prefix = f"{prefix}.{key}" if prefix else key
                if step_in:
                    if isinstance(current, list):
                        reached.extend(
                            (f"{prefix}.{index}" if prefix else str(index), element)
                            for index, element in enumerate(current)
                        )
                else:
                    reached.append((prefix, current))
            found = reached
        return found


    def _single(value, path):
        reached = _read_path(value, path)
        return reached[0][1] if len(reached) == 1 else None


    def _fetch(endpoint, headers):
        request = urllib.request.Request(endpoint, headers=dict(headers or {}), method="GET")
        opener = urllib.request.build_opener()
        opener.addheaders = []  # send the definition's headers, not urllib's default User-Agent
        try:
            with opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                status = response.status
                body = response.read()
        except urllib.error.HTTPError as error:
            return f"HTTP {error.code}", None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            return f"request failed: {getattr(error, 'reason', error)}", None
        if not 200 <= status < 300:
            return f"HTTP {status}", None
        try:
            return None, json.loads(body)
        except ValueError:
            return "response body is not JSON", None


    def fetch_source(source):
        source_id = source.get("id") if isinstance(source, dict) else None

        def failed(reason):
            return {"source_id": source_id, "status": "failed", "reason": reason}

        try:
            reason, data = _fetch(source["endpoint"], source.get("headers"))
            if reason is not None:
                return failed(reason)
            list_path = source.get("list_path")
            listed = data if list_path is None else _single(data, list_path)
            if not isinstance(listed, list):
                return failed(f"no list at {list_path!r}" if list_path else "response is not a list")
            id_path = source["id_path"]
            postings, seen = [], set()
            for index, element in enumerate(listed):
                if not isinstance(element, dict):
                    return failed(f"element {index} is not an object")
                raw_id = _single(element, id_path)
                if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)) or raw_id == "":
                    return failed(f"element {index} has no ID at {id_path!r}")
                posting_id = str(raw_id)
                if posting_id in seen:
                    continue
                seen.add(posting_id)
                postings.append({"posting_id": posting_id, "payload": element})
            return {"source_id": source_id, "status": "ok", "postings": postings}
        except Exception as error:  # the contract: never raises
            return failed(f"unexpected error: {type(error).__name__}: {error}")

    # --- end leaf code ---
    return fetch_source(source)


def fetch_sources__n2(sources):
    fetch_source = fetch_source__n5
    # --- glue, verbatim ---
    return [fetch_source(source) for source in sources]

    # --- end glue ---


def read_stated_text__n7(payload, source):
    # --- leaf n7 code, verbatim ---
    import html
    import re
    from html.parser import HTMLParser

    _FIELDS = ("title", "link", "location", "department_team", "full_text")
    _SINGLE = {"title", "link"}
    _BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption",
        "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main",
        "nav", "ol", "p", "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
    _SKIPPED_TAGS = {"script", "style"}


    def _read_path(value, path):
        """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
        found = [("", value)]
        for part in path.split("."):
            step_in = part.endswith("[]")
            key = part[:-2] if step_in else part
            reached = []
            for prefix, current in found:
                if key:
                    if not isinstance(current, dict) or key not in current:
                        continue
                    current = current[key]
                    prefix = f"{prefix}.{key}" if prefix else key
                if step_in:
                    if isinstance(current, list):
                        reached.extend(
                            (f"{prefix}.{index}" if prefix else str(index), element)
                            for index, element in enumerate(current)
                        )
                else:
                    reached.append((prefix, current))
            found = reached
        return found


    class _HtmlText(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.skipping = 0

        def handle_starttag(self, tag, attrs):
            if tag in _SKIPPED_TAGS:
                self.skipping += 1
            elif tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_startendtag(self, tag, attrs):
            if tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in _SKIPPED_TAGS:
                self.skipping = max(0, self.skipping - 1)
            elif tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_data(self, data):
            if not self.skipping:
                self.parts.append(re.sub(r"\s+", " ", data))


    def _from_html(markup):
        parser = _HtmlText()
        parser.feed(markup)
        parser.close()
        # Text split across inline tags arrives in pieces, so whitespace runs are collapsed after joining.
        lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).split("\n"))
        return "\n".join(line for line in lines if line)


    def _convert(text, text_format):
        if text_format == "html":
            return _from_html(text)
        if text_format == "escaped_html":
            return _from_html(html.unescape(text))
        return re.sub(r"\s+", " ", text).strip()


    def read_stated_text(payload, source):
        company = source.get("company")
        if isinstance(company, str) and company.strip():
            records = {"company": {"value": company, "evidence": [
                {"path": "source.company", "span": None, "raw": company, "value": company}
            ]}}
        else:
            records = {"company": {"value": None, "evidence": []}}

        locators_by_field = source.get("fields") or {}
        for field in _FIELDS:
            evidence, texts = [], []
            for locator in locators_by_field.get(field) or []:
                text_format = locator.get("format") or "plain"
                for path, raw in _read_path(payload, locator["path"]):
                    if not isinstance(raw, str) or not raw.strip():
                        continue
                    text = _convert(raw, text_format)
                    if not text or text in texts:
                        continue
                    texts.append(text)
                    evidence.append({"path": path, "span": None, "raw": raw, "value": text})
            if not texts:
                value = None
            elif field in _SINGLE:
                value = texts[0]
            else:
                value = texts
            records[field] = {"value": value, "evidence": evidence}

        return {name: records[name] for name in ("title", "link", "company", "location", "department_team", "full_text")}

    # --- end leaf code ---
    return read_stated_text(payload, source)


def derive_geography__n8(payload, source, location):
    # --- leaf n8 code, verbatim ---
    import html
    import re
    from html.parser import HTMLParser

    # ISO 3166-1 alpha-2 codes and the names that denote each one alone. Names shared with a US state
    # ('Georgia') or with another country ('Congo', 'Korea', 'Virgin Islands') are deliberately absent.
    _COUNTRIES = """
AD Andorra
AE United Arab Emirates|UAE
AF Afghanistan
AG Antigua and Barbuda
AI Anguilla
AL Albania
AM Armenia
AO Angola
AQ Antarctica
AR Argentina
AS American Samoa
AT Austria
AU Australia|New South Wales|Queensland|Tasmania|Northern Territory|Australian Capital Territory
AW Aruba
AX Åland Islands|Aland Islands
AZ Azerbaijan
BA Bosnia and Herzegovina|Bosnia
BB Barbados
BD Bangladesh
BE Belgium
BF Burkina Faso
BG Bulgaria
BH Bahrain
BI Burundi
BJ Benin
BL Saint Barthélemy|Saint Barthelemy
BM Bermuda
BN Brunei
BO Bolivia
BQ Caribbean Netherlands|Bonaire
BR Brazil|Brasil
BS Bahamas
BT Bhutan
BV Bouvet Island
BW Botswana
BY Belarus
BZ Belize
CA Canada|Ontario|Quebec|Québec|British Columbia|Alberta|Manitoba|Saskatchewan|Nova Scotia|New Brunswick|Newfoundland and Labrador|Newfoundland|Prince Edward Island|Yukon|Nunavut|Northwest Territories
CC Cocos (Keeling) Islands|Cocos Islands
CD Democratic Republic of the Congo|DR Congo|DRC
CF Central African Republic
CG Republic of the Congo|Congo-Brazzaville
CH Switzerland
CI Côte d'Ivoire|Cote d'Ivoire|Côte d’Ivoire|Cote d’Ivoire|Ivory Coast
CK Cook Islands
CL Chile
CM Cameroon
CN China|Mainland China
CO Colombia
CR Costa Rica
CU Cuba
CV Cape Verde|Cabo Verde
CW Curaçao|Curacao
CX Christmas Island
CY Cyprus
CZ Czechia|Czech Republic
DE Germany|Deutschland
DJ Djibouti
DK Denmark
DM Dominica
DO Dominican Republic
DZ Algeria
EC Ecuador
EE Estonia
EG Egypt
EH Western Sahara
ER Eritrea
ES Spain|España
ET Ethiopia
FI Finland
FJ Fiji
FK Falkland Islands
FM Micronesia
FO Faroe Islands
FR France
GA Gabon
GB United Kingdom|UK|U.K.|Great Britain|Britain|England|Scotland|Wales|Northern Ireland
GD Grenada
GE
GF French Guiana
GG Guernsey
GH Ghana
GI Gibraltar
GL Greenland
GM Gambia|The Gambia
GN Guinea
GP Guadeloupe
GQ Equatorial Guinea
GR Greece
GS South Georgia and the South Sandwich Islands
GT Guatemala
GU Guam
GW Guinea-Bissau
GY Guyana
HK Hong Kong
HM Heard Island and McDonald Islands
HN Honduras
HR Croatia
HT Haiti
HU Hungary
ID Indonesia
IE Ireland|Republic of Ireland
IL Israel
IM Isle of Man
IN India
IO British Indian Ocean Territory
IQ Iraq
IR Iran
IS Iceland
IT Italy|Italia
JE Jersey
JM Jamaica
JO Jordan
JP Japan
KE Kenya
KG Kyrgyzstan
KH Cambodia
KI Kiribati
KM Comoros
KN Saint Kitts and Nevis
KP North Korea
KR South Korea|Republic of Korea
KW Kuwait
KY Cayman Islands
KZ Kazakhstan
LA Laos
LB Lebanon
LC Saint Lucia
LI Liechtenstein
LK Sri Lanka
LR Liberia
LS Lesotho
LT Lithuania
LU Luxembourg
LV Latvia
LY Libya
MA Morocco
MC Monaco
MD Moldova
ME Montenegro
MF Saint Martin
MG Madagascar
MH Marshall Islands
MK North Macedonia|Macedonia
ML Mali
MM Myanmar|Burma
MN Mongolia
MO Macao|Macau
MP Northern Mariana Islands
MQ Martinique
MR Mauritania
MS Montserrat
MT Malta
MU Mauritius
MV Maldives
MW Malawi
MX Mexico|México
MY Malaysia
MZ Mozambique
NA Namibia
NC New Caledonia
NE Niger
NF Norfolk Island
NG Nigeria
NI Nicaragua
NL Netherlands|The Netherlands|Holland
NO Norway
NP Nepal
NR Nauru
NU Niue
NZ New Zealand
OM Oman
PA Panama
PE Peru
PF French Polynesia
PG Papua New Guinea
PH Philippines
PK Pakistan
PL Poland
PM Saint Pierre and Miquelon
PN Pitcairn Islands
PR Puerto Rico
PS Palestine
PT Portugal
PW Palau
PY Paraguay
QA Qatar
RE Réunion|Reunion
RO Romania
RS Serbia
RU Russia|Russian Federation
RW Rwanda
SA Saudi Arabia|KSA
SB Solomon Islands
SC Seychelles
SD Sudan
SE Sweden
SG Singapore
SH Saint Helena
SI Slovenia
SJ Svalbard and Jan Mayen
SK Slovakia
SL Sierra Leone
SM San Marino
SN Senegal
SO Somalia
SR Suriname
SS South Sudan
ST São Tomé and Príncipe|Sao Tome and Principe
SV El Salvador
SX Sint Maarten
SY Syria
SZ Eswatini|Swaziland
TC Turks and Caicos Islands
TD Chad
TF French Southern Territories
TG Togo
TH Thailand
TJ Tajikistan
TK Tokelau
TL Timor-Leste|East Timor
TM Turkmenistan
TN Tunisia
TO Tonga
TR Turkey|Türkiye|Turkiye
TT Trinidad and Tobago
TV Tuvalu
TW Taiwan
TZ Tanzania
UA Ukraine
UG Uganda
UM United States Minor Outlying Islands
US United States|United States of America|USA|U.S.|U.S.A.|New England
UY Uruguay
UZ Uzbekistan
VA Vatican City|Holy See
VC Saint Vincent and the Grenadines
VE Venezuela
VG British Virgin Islands
VI U.S. Virgin Islands|US Virgin Islands
VN Vietnam|Viet Nam
VU Vanuatu
WF Wallis and Futuna
WS Samoa
YE Yemen
YT Mayotte
ZA South Africa
ZM Zambia
ZW Zimbabwe
"""

    # US states and DC by full name (Georgia omitted: it is also a country) and postal abbreviation.
    _US_STATE_NAMES = (
        "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Hawaii|Idaho|"
        "Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|"
        "Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|"
        "North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
        "South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|"
        "District of Columbia|Washington, D.C.|Washington DC"
    ).split("|")
    _US_STATE_CODES = set(
        "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
        "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
    )

    # Region names and synonyms; a few name two regions.
    _REGION_NAMES = {
        "north america": ["north_america"], "namer": ["north_america"], "noram": ["north_america"],
        "NA": ["north_america"],
        "americas": ["americas"], "the americas": ["americas"], "amer": ["americas"], "amers": ["americas"],
        "latin america": ["latin_america"], "latam": ["latin_america"], "south america": ["latin_america"],
        "central america": ["latin_america"], "caribbean": ["latin_america"],
        "emea": ["emea"],
        "europe": ["europe"], "european union": ["europe"], "EU": ["europe"], "western europe": ["europe"],
        "eastern europe": ["europe"], "central europe": ["europe"], "northern europe": ["europe"],
        "southern europe": ["europe"], "nordics": ["europe"], "nordic": ["europe"],
        "scandinavia": ["europe"], "dach": ["europe"], "benelux": ["europe"], "CEE": ["europe"],
        "european economic area": ["europe"], "EEA": ["europe"],
        "middle east": ["middle_east"], "GCC": ["middle_east"],
        "mena": ["middle_east", "africa"], "menat": ["middle_east", "africa"],
        "africa": ["africa"], "sub-saharan africa": ["africa"], "north africa": ["africa"],
        "west africa": ["africa"], "east africa": ["africa"], "southern africa": ["africa"],
        "apac": ["apac"], "asia-pacific": ["apac"], "asia pacific": ["apac"], "asia/pacific": ["apac"],
        "APJ": ["apac"],
        "asia": ["asia"], "southeast asia": ["asia"], "south-east asia": ["asia"], "south asia": ["asia"],
        "east asia": ["asia"], "central asia": ["asia"],
        "oceania": ["oceania"], "australasia": ["oceania"], "ANZ": ["oceania"],
    }

    # Each country's most specific regions.
    _REGION_MEMBERS = {
        "north_america": "US CA MX BM GL PM UM",
        "latin_america": (
            "MX BZ CR SV GT HN NI PA AR BO BR CL CO EC GY PE PY SR UY VE FK GF CU DO HT JM PR BS BB TT AG "
            "DM GD KN LC VC AI AW BQ CW SX KY TC VG VI MF BL GP MQ MS"
        ),
        "europe": (
            "AD AL AT AX BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT "
            "LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM UA VA TR AM AZ GE"
        ),
        "middle_east": "AE BH IL IQ IR JO KW LB OM PS QA SA SY YE TR EG",
        "africa": (
            "DZ AO BJ BW BF BI CV CM CF TD KM CD CG CI DJ EG GQ ER SZ ET GA GM GH GN GW KE LS LR LY MG MW "
            "ML MR MU YT MA MZ NA NE NG RE RW SH ST SN SC SL SO ZA SS SD TZ TG TN UG EH ZM ZW"
        ),
        "asia": (
            "AF BD BT BN KH CN HK IN ID JP KZ KG LA MO MY MV MN MM NP KP KR PK PH SG LK TW TJ TH TL TM UZ "
            "VN AM AZ GE IO CX CC"
        ),
        "oceania": "AU NZ FJ PG SB VU NC PF WS TO TV KI NR MH FM PW CK NU TK WF AS GU MP NF PN HM",
    }


    def _build_tables():
        codes = set()
        names = {}  # casefolded name -> ("country", code) or ("region", [regions])
        upper_tokens = {}  # exact upper-case token -> same
        for line in _COUNTRIES.strip().splitlines():
            code, _, rest = line.partition(" ")
            codes.add(code)
            for name in filter(None, rest.split("|")):
                if len(name) <= 3 and name.isalpha():
                    upper_tokens[name] = ("country", code)
                else:
                    names[name.casefold()] = ("country", code)
        for name in _US_STATE_NAMES:
            names[name.casefold()] = ("country", "US")
        for name, regions in _REGION_NAMES.items():
            if name.isupper():
                upper_tokens[name] = ("region", regions)
            else:
                names[name.casefold()] = ("region", regions)
        for code in codes - _US_STATE_CODES:
            upper_tokens.setdefault(code, ("country", code))
        for code in _US_STATE_CODES - codes:
            upper_tokens.setdefault(code, ("country", "US"))
        regions_of = {}
        for region, members in _REGION_MEMBERS.items():
            for code in members.split():
                regions_of.setdefault(code, []).append(region)
        return codes, names, upper_tokens, regions_of


    _CODES, _NAMES, _UPPER_TOKENS, _REGIONS_OF = _build_tables()
    _NAME_PATTERN = re.compile(
        r"(?<![^\W_])("
        + "|".join(re.escape(name) for name in sorted(_NAMES, key=len, reverse=True))
        + r")(?![^\W_])",
        re.IGNORECASE,
    )
    _TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,3})(?![A-Za-z0-9])")


    def _scan(text):
        """Every (span, matched text, kind, target) a text names, names first, then upper-case codes."""
        found, taken = [], []
        for match in _NAME_PATTERN.finditer(text):
            kind, target = _NAMES[match.group(1).casefold()]
            found.append((match.span(1), match.group(1), kind, target))
            taken.append(match.span(1))
        for match in _TOKEN_PATTERN.finditer(text):
            start, end = match.span(1)
            if match.group(1) not in _UPPER_TOKENS or any(s < end and start < e for s, e in taken):
                continue
            kind, target = _UPPER_TOKENS[match.group(1)]
            found.append(((start, end), match.group(1), kind, target))
        return sorted(found, key=lambda item: item[0])


    # Text conversion, the same as read_stated_text's, so that spans index a locator's value as converted
    # to plain text.
    _BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption",
        "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main",
        "nav", "ol", "p", "pre", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
    _SKIPPED_TAGS = {"script", "style"}


    class _HtmlText(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.skipping = 0

        def handle_starttag(self, tag, attrs):
            if tag in _SKIPPED_TAGS:
                self.skipping += 1
            elif tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_startendtag(self, tag, attrs):
            if tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in _SKIPPED_TAGS:
                self.skipping = max(0, self.skipping - 1)
            elif tag in _BLOCK_TAGS:
                self.parts.append("\n")

        def handle_data(self, data):
            if not self.skipping:
                self.parts.append(re.sub(r"\s+", " ", data))


    def _from_html(markup):
        parser = _HtmlText()
        parser.feed(markup)
        parser.close()
        # Text split across inline tags arrives in pieces, so whitespace runs are collapsed after joining.
        lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).split("\n"))
        return "\n".join(line for line in lines if line)


    def _convert(text, text_format):
        if text_format == "html":
            return _from_html(text)
        if text_format == "escaped_html":
            return _from_html(html.unescape(text))
        return re.sub(r"\s+", " ", text).strip()


    def _whole_value(text):
        """A countries-locator value read whole: an ISO code by declaration, or a name."""
        stripped = text.strip()
        if len(stripped) == 2 and stripped.upper() in _CODES:
            return [("country", stripped.upper())]
        named = _NAMES.get(stripped.casefold()) or _UPPER_TOKENS.get(stripped)
        return [named] if named else []


    def _read_path(value, path):
        """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
        found = [("", value)]
        for part in path.split("."):
            step_in = part.endswith("[]")
            key = part[:-2] if step_in else part
            reached = []
            for prefix, current in found:
                if key:
                    if not isinstance(current, dict) or key not in current:
                        continue
                    current = current[key]
                    prefix = f"{prefix}.{key}" if prefix else key
                if step_in:
                    if isinstance(current, list):
                        reached.extend(
                            (f"{prefix}.{index}" if prefix else str(index), element)
                            for index, element in enumerate(current)
                        )
                else:
                    reached.append((prefix, current))
            found = reached
        return found


    def derive_geography(payload, source, location):
        country_evidence, region_evidence = [], []

        def add(kind, target, path, span, raw):
            if kind == "country":
                country_evidence.append({"path": path, "span": span, "raw": raw, "value": target})
            else:
                for region in target:
                    region_evidence.append({"path": path, "span": span, "raw": raw, "value": region})

        for locator in (source.get("fields") or {}).get("countries") or []:
            text_format = locator.get("format") or "plain"
            for path, raw in _read_path(payload, locator["path"]):
                if not isinstance(raw, str) or not raw.strip():
                    continue
                text = _convert(raw, text_format)
                whole = _whole_value(text)
                if whole:
                    for kind, target in whole:
                        add(kind, target, path, None, raw)
                    continue
                matches = _scan(text)
                if not matches:
                    country_evidence.append({"path": path, "span": None, "raw": raw, "value": None})
                for (start, end), matched, kind, target in matches:
                    add(kind, target, path, [start, end], matched)

        for entry in (location or {}).get("evidence") or []:
            text = entry.get("value")
            if not isinstance(text, str):
                continue
            for (start, end), matched, kind, target in _scan(text):
                add(kind, target, entry["path"], [start, end], matched)

        for entry in [e for e in country_evidence if e["value"] is not None]:
            for region in _REGIONS_OF.get(entry["value"], []):
                region_evidence.append({**entry, "value": region})

        countries = sorted({e["value"] for e in country_evidence if e["value"] is not None})
        regions = sorted({e["value"] for e in region_evidence})
        return {
            "countries": {"value": countries or None, "evidence": country_evidence},
            "regions": {"value": regions or None, "evidence": region_evidence},
        }

    # --- end leaf code ---
    return derive_geography(payload, source, location)


def derive_work_arrangement__n9(payload, source, location):
    # --- leaf n9 code, verbatim ---
    import json
    import re

    _DECLARED = {"remote", "hybrid", "onsite"}
    _WORDS = [
        ("remote", re.compile(r"(?<![^\W_])remote(?![^\W_])", re.IGNORECASE)),
        ("hybrid", re.compile(r"(?<![^\W_])hybrid(?![^\W_])", re.IGNORECASE)),
        ("onsite", re.compile(r"(?<![^\W_])(?:on-site|onsite|in-office|in\s+office)(?![^\W_])", re.IGNORECASE)),
    ]


    def _read_path(value, path):
        """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
        found = [("", value)]
        for part in path.split("."):
            step_in = part.endswith("[]")
            key = part[:-2] if step_in else part
            reached = []
            for prefix, current in found:
                if key:
                    if not isinstance(current, dict) or key not in current:
                        continue
                    current = current[key]
                    prefix = f"{prefix}.{key}" if prefix else key
                if step_in:
                    if isinstance(current, list):
                        reached.extend(
                            (f"{prefix}.{index}" if prefix else str(index), element)
                            for index, element in enumerate(current)
                        )
                else:
                    reached.append((prefix, current))
            found = reached
        return found


    def _as_key(raw):
        return raw if isinstance(raw, str) else json.dumps(raw)


    def derive_work_arrangement(payload, source, location):
        evidence, value = [], None
        for locator in (source.get("fields") or {}).get("work_arrangement") or []:
            values = locator.get("values") or {}
            for path, raw in _read_path(payload, locator["path"]):
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    continue
                mapped = values.get(_as_key(raw))
                if mapped not in _DECLARED:
                    mapped = None
                evidence.append({"path": path, "span": None, "raw": raw, "value": mapped})
                if value is None and mapped is not None:
                    value = mapped
        if value is not None:
            return {"value": value, "evidence": evidence}

        matches = []
        for entry in (location or {}).get("evidence") or []:
            text = entry.get("value")
            if not isinstance(text, str):
                continue
            for arrangement, pattern in _WORDS:
                for match in pattern.finditer(text):
                    matches.append({"path": entry["path"], "span": [match.start(), match.end()],
                                    "raw": match.group(0), "value": arrangement})
        named = {match["value"] for match in matches}
        value = named.pop() if len(named) == 1 else None
        return {"value": value, "evidence": evidence + matches}

    # --- end leaf code ---
    return derive_work_arrangement(payload, source, location)


def derive_employment_type__n10(payload, source, title):
    # --- leaf n10 code, verbatim ---
    import json
    import re

    _DECLARED = {"full-time", "part-time", "contract", "temporary", "internship"}
    _EDGE_BEFORE = r"(?<![^\W_])"
    _EDGE_AFTER = r"(?![^\W_])"
    # Title words that name the posting's own employment type. 'Contract' alone usually names the
    # subject of the work ('Contracts Manager', 'Contract Specialist'), so it counts only when set off
    # from the role: in brackets, or after a separator at the end of the title.
    _TITLE_WORDS = [
        ("internship", re.compile(_EDGE_BEFORE + r"(?:internship|interns?)" + _EDGE_AFTER, re.IGNORECASE)),
        ("contract", re.compile(_EDGE_BEFORE + r"contractor" + _EDGE_AFTER, re.IGNORECASE)),
        ("contract", re.compile(r"[(\[]\s*contract\s*[)\]]|[-–—,|:]\s*contract\s*$", re.IGNORECASE)),
        ("part-time", re.compile(_EDGE_BEFORE + r"part[\s-]time" + _EDGE_AFTER, re.IGNORECASE)),
        ("temporary", re.compile(_EDGE_BEFORE + r"temporary" + _EDGE_AFTER, re.IGNORECASE)),
        ("temporary", re.compile(r"[(\[]\s*temp\s*[)\]]", re.IGNORECASE)),
        ("full-time", re.compile(_EDGE_BEFORE + r"full[\s-]time" + _EDGE_AFTER, re.IGNORECASE)),
    ]
    # Phrases in which a listed word names the work rather than its terms. They are matched first and
    # consume their text, so the word inside them yields nothing.
    _NOT_TYPES = re.compile(
        _EDGE_BEFORE
        + r"(?:internships?\s+programs?|interns?\s+programs?|intern\s+recruit(?:er|ers|ing|ment)|"
        r"full[\s-]time\s+equivalents?|temporary\s+(?:housing|accommodation|staffing|agency))"
        + _EDGE_AFTER,
        re.IGNORECASE,
    )


    def _read_path(value, path):
        """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
        found = [("", value)]
        for part in path.split("."):
            step_in = part.endswith("[]")
            key = part[:-2] if step_in else part
            reached = []
            for prefix, current in found:
                if key:
                    if not isinstance(current, dict) or key not in current:
                        continue
                    current = current[key]
                    prefix = f"{prefix}.{key}" if prefix else key
                if step_in:
                    if isinstance(current, list):
                        reached.extend(
                            (f"{prefix}.{index}" if prefix else str(index), element)
                            for index, element in enumerate(current)
                        )
                else:
                    reached.append((prefix, current))
            found = reached
        return found


    def _as_key(raw):
        return raw if isinstance(raw, str) else json.dumps(raw)


    def derive_employment_type(payload, source, title):
        evidence, value = [], None
        for locator in (source.get("fields") or {}).get("employment_type") or []:
            values = locator.get("values") or {}
            for path, raw in _read_path(payload, locator["path"]):
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    continue
                mapped = values.get(_as_key(raw))
                if mapped not in _DECLARED:
                    mapped = None
                evidence.append({"path": path, "span": None, "raw": raw, "value": mapped})
                if value is None and mapped is not None:
                    value = mapped
        if value is not None:
            return {"value": value, "evidence": evidence}

        title = title or {}
        text = title.get("value")
        if not isinstance(text, str):
            return {"value": None, "evidence": evidence}
        path = next((e["path"] for e in title.get("evidence") or [] if e.get("value") == text), "title")
        matches, taken = [], [match.span() for match in _NOT_TYPES.finditer(text)]
        for employment_type, pattern in _TITLE_WORDS:
            for match in pattern.finditer(text):
                span = match.span()
                if any(s < span[1] and span[0] < e for s, e in taken):
                    continue
                taken.append(span)
                matches.append({"path": path, "span": list(span), "raw": match.group(0), "value": employment_type})
        named = {match["value"] for match in matches}
        value = named.pop() if len(named) == 1 else None
        return {"value": value, "evidence": evidence + sorted(matches, key=lambda m: m["span"])}

    # --- end leaf code ---
    return derive_employment_type(payload, source, title)


def derive_seniority__n11(title):
    # --- leaf n11 code, verbatim ---
    import re

    _EDGE_BEFORE = r"(?<![^\W_])"
    _EDGE_AFTER = r"(?![^\W_])"

    # Phrases in which a level word names something other than a level. They are matched first and
    # consume their text, so the level word inside them yields nothing.
    _NOT_LEVELS = re.compile(
        _EDGE_BEFORE
        + r"(?:chief\s+of\s+staff|staff\s+accountant|staff\s+nurse|staff\s+writer|support\s+staff|"
        r"medical\s+staff|lead\s+generation|lead\s+gen|lead\s+qualification)"
        + _EDGE_AFTER,
        re.IGNORECASE,
    )

    # Each level and the words or phrases that denote it.
    _LEVELS = [
        ("executive", r"chief\s+[\w\s&,-]*?officer|vice\s+president|svp|evp|avp|vp"),
        ("director", r"director"),
        ("manager", r"manager|mgr"),
        ("principal", r"principal"),
        ("staff", r"staff"),
        ("lead", r"lead"),
        ("senior", r"senior|sr\.?"),
        ("junior", r"junior|jr\.?|entry[\s-]level"),
        ("intern", r"internship|intern"),
    ]
    _PATTERN = re.compile(
        "|".join(f"(?P<{level}>{_EDGE_BEFORE}(?:{words})(?![^\\W_]))" for level, words in _LEVELS),
        re.IGNORECASE,
    )


    def derive_seniority(title):
        title = title or {}
        text = title.get("value")
        if not isinstance(text, str):
            return {"value": None, "evidence": []}
        path = next((e["path"] for e in title.get("evidence") or [] if e.get("value") == text), "title")

        excluded = [match.span() for match in _NOT_LEVELS.finditer(text)]
        evidence = []
        for match in _PATTERN.finditer(text):
            start, end = match.span()
            if any(s < end and start < e for s, e in excluded):
                continue
            evidence.append({"path": path, "span": [start, end], "raw": match.group(0), "value": match.lastgroup})
        levels = sorted({entry["value"] for entry in evidence})
        return {"value": levels or None, "evidence": evidence}

    # --- end leaf code ---
    return derive_seniority(title)


def derive_salary__n12(full_text, countries, pay_floors):
    # --- leaf n12 code, verbatim ---
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

    # --- end leaf code ---
    return derive_salary(full_text, countries, pay_floors)


def derive_years_of_experience__n13(full_text):
    # --- leaf n13 code, verbatim ---
    import re

    _WORDS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    }
    _N = r"(?<![\w.])(?:\d{1,2}|" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")(?![\w.])"
    _YEARS = r"(?:years?|yrs?)\b"
    _DASH = r"(?:-|–|—|to)"
    # Each alternative states a minimum number of years; the named group holds that minimum.
    _REQUIREMENT = re.compile(
        "|".join([
            rf"\b(?:at\s+least\s+|(?:a\s+)?minimum\s+(?:of\s+)?)(?P<least>{_N})\s*\+?\s*{_YEARS}",
            rf"(?P<range>{_N})\s*{_DASH}\s*{_N}\s*\+?\s*{_YEARS}",
            rf"(?P<plus>{_N})\s*\+\s*{_YEARS}",
            rf"(?P<more>{_N})\s+or\s+more\s+{_YEARS}",
            rf"(?P<of>{_N})\s+{_YEARS}(?:['’]?\s+experience\b|\s+of\s+(?:[\w-]+\s+){{0,4}}?experience\b)",
        ]),
        re.IGNORECASE,
    )


    def _to_int(text):
        text = text.lower()
        return int(text) if text.isdigit() else _WORDS[text]


    def derive_years_of_experience(full_text):
        evidence = []
        for entry in (full_text or {}).get("evidence") or []:
            text = entry.get("value")
            if not isinstance(text, str):
                continue
            for match in _REQUIREMENT.finditer(text):
                minimum = _to_int(next(group for group in match.groups() if group is not None))
                evidence.append({"path": entry["path"], "span": list(match.span()),
                                 "raw": match.group(0), "value": minimum})
        if not evidence:
            return {"value": None, "evidence": []}
        return {"value": min(entry["value"] for entry in evidence), "evidence": evidence}

    # --- end leaf code ---
    return derive_years_of_experience(full_text)


def read_posted_date__n14(payload, source):
    # --- leaf n14 code, verbatim ---
    import datetime
    import re

    _ISO_8601 = re.compile(
        r"(\d{4})-(\d{2})-(\d{2})"
        r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?(?:Z|[+-]\d{2}(?::?\d{2})?)?)?"
    )


    def _read_path(value, path):
        """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
        found = [("", value)]
        for part in path.split("."):
            step_in = part.endswith("[]")
            key = part[:-2] if step_in else part
            reached = []
            for prefix, current in found:
                if key:
                    if not isinstance(current, dict) or key not in current:
                        continue
                    current = current[key]
                    prefix = f"{prefix}.{key}" if prefix else key
                if step_in:
                    if isinstance(current, list):
                        reached.extend(
                            (f"{prefix}.{index}" if prefix else str(index), element)
                            for index, element in enumerate(current)
                        )
                else:
                    reached.append((prefix, current))
            found = reached
        return found


    def _parse(raw, date_format):
        if date_format == "iso8601":
            if not isinstance(raw, str):
                return None
            match = _ISO_8601.fullmatch(raw.strip())
            if not match:
                return None
            year, month, day = (int(part) for part in match.groups())
            return datetime.date(year, month, day).isoformat()
        if date_format == "epoch_millis":
            if isinstance(raw, bool):
                return None
            if isinstance(raw, str) and re.fullmatch(r"\d+", raw.strip()):
                raw = int(raw.strip())
            if not isinstance(raw, (int, float)):
                return None
            moment = datetime.datetime.fromtimestamp(raw / 1000, tz=datetime.timezone.utc)
            return moment.date().isoformat()
        return None


    def read_posted_date(payload, source):
        date = source.get("date")
        if not date:
            return {"value": None, "evidence": []}
        reached = [(path, raw) for path, raw in _read_path(payload, date["path"]) if raw is not None]
        if not reached:
            return {"value": None, "evidence": []}
        path, raw = reached[0]
        try:
            value = _parse(raw, date.get("format"))
        except (ValueError, OverflowError, OSError):
            value = None
        return {"value": value, "evidence": [{"path": path, "span": None, "raw": raw, "value": value}]}

    # --- end leaf code ---
    return read_posted_date(payload, source)


def extract_posting__n6(payload, source, pay_floors):
    read_stated_text = read_stated_text__n7
    derive_geography = derive_geography__n8
    derive_work_arrangement = derive_work_arrangement__n9
    derive_employment_type = derive_employment_type__n10
    derive_seniority = derive_seniority__n11
    derive_salary = derive_salary__n12
    derive_years_of_experience = derive_years_of_experience__n13
    read_posted_date = read_posted_date__n14
    # --- glue, verbatim ---
    stated = read_stated_text(payload, source)
    geography = derive_geography(payload, source, stated["location"])
    return {
        **stated,
        **geography,
        "work_arrangement": derive_work_arrangement(payload, source, stated["location"]),
        "employment_type": derive_employment_type(payload, source, stated["title"]),
        "seniority": derive_seniority(stated["title"]),
        "salary": derive_salary(stated["full_text"], geography["countries"], pay_floors),
        "years_of_experience": derive_years_of_experience(stated["full_text"]),
        "posted_date": read_posted_date(payload, source),
    }

    # --- end glue ---


def extract_fetched__n3(fetch_results, sources, pay_floors):
    extract_posting = extract_posting__n6
    # --- glue, verbatim ---
    source_by_id = {source["id"]: source for source in sources}
    extracted_results = []
    for result in fetch_results:
        if result["status"] != "ok":
            extracted_results.append(result)
            continue
        source = source_by_id[result["source_id"]]
        postings = [
            {**posting, "fields": extract_posting(posting["payload"], source, pay_floors)}
            for posting in result["postings"]
        ]
        extracted_results.append({**result, "postings": postings})
    return extracted_results

    # --- end glue ---


def merge_into_store__n4(stored_postings, extracted_results, as_of):
    # --- leaf n4 code, verbatim ---
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

    # --- end leaf code ---
    return merge_into_store(stored_postings, extracted_results, as_of)


def root__n1(sources, stored_postings, pay_floors, as_of):
    fetch_sources = fetch_sources__n2
    extract_fetched = extract_fetched__n3
    merge_into_store = merge_into_store__n4
    # --- glue, verbatim ---
    fetch_results = fetch_sources(sources)
    extracted_results = extract_fetched(fetch_results, sources, pay_floors)
    return merge_into_store(stored_postings, extracted_results, as_of)

    # --- end glue ---


if __name__ == "__main__":
    import json
    import sys
    args = json.loads(sys.stdin.read())
    print(json.dumps(root__n1(**args), default=str))
