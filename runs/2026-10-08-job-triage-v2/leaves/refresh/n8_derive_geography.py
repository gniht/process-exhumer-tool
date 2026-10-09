import re

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
        for path, raw in _read_path(payload, locator["path"]):
            if not isinstance(raw, str) or not raw.strip():
                continue
            whole = _whole_value(raw)
            if whole:
                for kind, target in whole:
                    add(kind, target, path, None, raw)
                continue
            matches = _scan(raw)
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
