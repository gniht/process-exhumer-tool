"""Writes the job-triage v2 stage-2 node trees. Shared descriptions are defined once so the
interface between refresh and assess (the stored postings) is the same text everywhere."""
import ast
import json
import os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATH = (
    "A path is a dotted sequence of keys into JSON; a key followed by [] steps into every element of the "
    "list there (e.g. 'departments[].name', 'categories.allLocations[]'). In evidence, a path names the one "
    "element read, by index (e.g. 'departments.0.name'); a path beginning 'source.' names a value in the "
    "source definition rather than the payload."
)
EVIDENCE = (
    "An evidence entry is {path, span, raw, value}: path locates what was read; span is [start, end) "
    "character offsets into the text at that path as converted to plain text, or null when the whole value "
    "at the path was used; raw is the board's value at the path, or the matched text when span is given; "
    "value is what the entry contributes to the field, a value from the field's declared value space, or "
    "null when the board's value could not be mapped into it."
)
FIELD_RECORD = (
    "A field record is {value, evidence}: value is a value from the field's declared value space, or null "
    "for unknown; evidence lists the entries the value was derived from, including board values that could "
    "not be mapped (value null)."
)
REGIONS = (
    "Regions: africa, americas, apac, asia, emea, europe, latin_america, middle_east, north_america, "
    "oceania; americas contains north_america and latin_america, emea contains europe, middle_east and "
    "africa, apac contains asia and oceania."
)
FIELDS = (
    "Declared fields and their value spaces: "
    "title and link (the posting's page address), each a string as stated; "
    "company, a string from the source definition (evidence path 'source.company'); "
    "location, department_team and full_text, each a list of strings as stated, in board order, one per "
    "piece of text read, with one evidence entry per piece (department_team's values describe the posting "
    "together, not as alternatives); "
    "countries, a sorted list of distinct ISO 3166-1 alpha-2 codes, stated or clearly derivable; "
    "regions, a sorted list of distinct regions, each stated or implied by a listed country (a country "
    "implies its most specific regions; a region never implies a country); "
    "work_arrangement, one of 'remote', 'hybrid', 'onsite'; "
    "employment_type, one of 'full-time', 'part-time', 'contract', 'temporary', 'internship'; "
    "seniority, a sorted list of distinct levels named by title words, from 'intern', 'junior', 'senior', "
    "'staff', 'principal', 'lead', 'manager', 'director', 'executive' (no seniority word means unknown, not "
    "mid-level); "
    "salary, {minimum, maximum, currency, pay_period}, numbers with minimum <= maximum, currency an ISO 4217 "
    "code or null, pay_period one of 'hour', 'day', 'week', 'month', 'year' or null; "
    "years_of_experience, a non-negative integer, the lowest number of years the posting states as a "
    "requirement; "
    "posted_date, 'YYYY-MM-DD', null meaning undated. "
    "A list-valued field is never an empty list: with nothing recognisable it is null. "
    + REGIONS + " " + FIELD_RECORD + " " + EVIDENCE + " " + PATH
)
FIELD_NAMES = (
    "title, link, company, location, department_team, full_text, countries, regions, work_arrangement, "
    "employment_type, seniority, salary, years_of_experience, posted_date"
)
STORE_TYPE = (
    "a list of stored-posting entries sorted by source_id then posting_id, at most one per (source_id, "
    "posting_id), possibly empty"
)
STORE_DESC = (
    "The shared memory of every posting ever fetched; nothing is removed from it. Each entry is "
    "{source_id, posting_id, first_seen, listing, payload, fields}: source_id the id of the source "
    "definition it was fetched from; posting_id the board's posting ID as a string; first_seen the date it "
    "was first stored, 'YYYY-MM-DD'; listing {status, since}, status 'listed' or 'no_longer_listed', since "
    "the date it was first missed when no longer listed and otherwise null; payload the board's raw posting "
    "object from the most recent successful fetch that listed it; fields a map from each declared field "
    "name (" + FIELD_NAMES + ") to a field record. " + FIELDS
)
SOURCE_DESC = (
    "Each definition is {id, company, endpoint, headers, list_path, id_path, date, fields}: id a string "
    "naming the source, distinct across the list; company the employer's name; endpoint the URL fetched "
    "with GET, returning JSON; headers a map of request headers sent with the request, possibly empty; "
    "list_path the path to the list of postings in the response, or null when the response itself is the "
    "list; id_path the path within a posting to its board ID; date {path, format} locating the posting date, "
    "format 'iso8601' or 'epoch_millis', or null when the board gives none; fields a map from field name "
    "(title, link, location, department_team, full_text, countries, work_arrangement, employment_type) to a "
    "list of locators {path, format, values}: format ('plain' by default, 'html', or 'escaped_html' for HTML "
    "whose markup is itself entity-escaped) says how text at the path is converted, and values, for "
    "work_arrangement and employment_type, maps board values (strings; other JSON values as their JSON "
    "text, e.g. 'true') to the field's declared values, a board value absent from the map being left "
    "unmapped. " + PATH
)
FETCH_RESULT_DESC = (
    "One result per source: {source_id, status: 'ok', postings}, postings a list of {posting_id, payload} "
    "in response order, posting_id the board's ID as a string, distinct within the result, payload the "
    "posting object unchanged; or {source_id, status: 'failed', reason}, reason a string saying what went "
    "wrong."
)
EXTRACTED_RESULT_DESC = (
    "Fetch results with extraction added: {source_id, status: 'ok', postings}, postings a list of "
    "{posting_id, payload, fields} in response order, posting_id distinct within the result, fields a map "
    "from each declared field name (" + FIELD_NAMES + ") to a field record; or {source_id, status: "
    "'failed', reason}. " + FIELDS
)
REPORT_DESC = (
    "One record per source, in the order given: {source_id, status: 'ok', listed, new, no_longer_listed, "
    "listed_again}, non-negative integer counts of postings the fetch listed, postings not previously "
    "stored, postings that became no longer listed in this run, and postings previously no longer listed "
    "that are listed again; or {source_id, status: 'failed', reason}."
)
AS_OF = {
    "name": "as_of",
    "type": "a date, 'YYYY-MM-DD'",
    "description": "The current date. Every date the run records or measures from is this one.",
}
PAY_FLOORS = {
    "name": "pay_floors",
    "type": "a map from ISO 4217 currency code to a positive number in that currency",
    "description": (
        "For each currency, the lowest lower figure at which a salary range with no stated pay period is "
        "read as yearly: the full-time yearly equivalent of the minimum wage where that currency is paid. "
        "Below the floor, or for a currency with no entry, an unstated pay period is unknown. Data rather "
        "than code, so a place can be added without the contract changing."
    ),
}
STORE_IN = {"name": "stored_postings", "type": STORE_TYPE, "description": STORE_DESC}
SOURCE = {"name": "source", "type": "a source definition", "description": SOURCE_DESC}
PAYLOAD = {"name": "payload", "type": "a JSON object", "description": "One posting object exactly as the board returned it."}


def rec(name, desc):
    return {"name": name, "type": "a field record", "description": desc + " " + FIELDS}


# ---------------------------------------------------------------- refresh

REFRESH_BEHAVIOR = json.load(open(os.path.join(RUN, "root-contract-refresh.json")))["behavior"]

refresh_root = {
    "behavior": REFRESH_BEHAVIOR,
    "inputs": [
        {
            "name": "sources",
            "type": "a list of source definitions with distinct ids",
            "description": "The sources to fetch. " + SOURCE_DESC + " Data rather than code, so sources can be added without the contract changing.",
        },
        STORE_IN,
        PAY_FLOORS,
        AS_OF,
    ],
    "outputs": [
        {"name": "updated_postings", "type": STORE_TYPE,
         "description": "The successor to the incoming stored postings, in exactly the same shape. " + STORE_DESC},
        {"name": "source_report", "type": "a list of per-source records", "description": REPORT_DESC},
    ],
}

fetch_sources = {
    "behavior": (
        "Given a list of source definitions: the result list has exactly one result per source, in the same "
        "order, each naming its source's id; each result is what fetching that source alone yields, so one "
        "source's failure leaves every other source's result unaffected; a fetch that succeeds yields every "
        "posting the response lists, keyed by the board's posting ID; a fetch that fails yields the reason "
        "and no postings."
    ),
    "inputs": [{"name": "sources", "type": "a list of source definitions with distinct ids", "description": SOURCE_DESC}],
    "outputs": [{"name": "fetch_results", "type": "a list of fetch results", "description": FETCH_RESULT_DESC}],
}

fetch_source = {
    "behavior": (
        "Given one source definition: sends one GET request to its endpoint carrying exactly its headers, "
        "with a bounded timeout, and never raises. It returns status 'ok' only when the response is HTTP "
        "2xx, its body parses as JSON, the value at list_path (the whole body when list_path is null) is a "
        "list, and every element is an object holding a string or integer at id_path; postings then holds "
        "one {posting_id, payload} per element in response order, posting_id the ID as a string and payload "
        "the element unchanged, an element whose ID repeats an earlier element's being omitted. Otherwise it "
        "returns status 'failed' with a reason naming what went wrong: a network error or timeout, the HTTP "
        "status, an unparseable body, a missing or non-list value at list_path, or an element without an ID."
    ),
    "inputs": [SOURCE],
    "outputs": [{"name": "fetch_result", "type": "a fetch result", "description": FETCH_RESULT_DESC}],
}

MAPPING = (
    "a board's value being mapped into a value space only by the source definition's value maps and date "
    "format, or by the program's fixed tables of names, words and forms, which decide: what they do not "
    "cover is unknown, and an entry counts wherever it appears"
)
SALARY_RULE = (
    "a salary being extracted only where the posting states it in a recognisable form, a bare $ being read "
    "as USD only where the US is the posting's only country, and a pay period the posting does not state "
    "being read as yearly only where the salary's currency has a pay-floor entry and the lower figure is at "
    "least that floor, and otherwise unknown"
)

extract_fetched = {
    "behavior": (
        "Given fetch results, the source definitions they name and a pay-floor table: returns the results in "
        "the same order and otherwise unchanged, except that every posting of every 'ok' result gains "
        "fields, the extraction of its payload under its own source's definition and the pay-floor table: a "
        "field record for every declared field, each value within its field's declared value space or null "
        "and carrying the evidence it was derived from, " + MAPPING + "; " + SALARY_RULE + "; failed results "
        "pass through unchanged."
    ),
    "inputs": [
        {"name": "fetch_results", "type": "a list of fetch results, each naming a source in sources", "description": FETCH_RESULT_DESC},
        {"name": "sources", "type": "a list of source definitions with distinct ids", "description": SOURCE_DESC},
        PAY_FLOORS,
    ],
    "outputs": [{"name": "extracted_results", "type": "a list of extracted results", "description": EXTRACTED_RESULT_DESC}],
}

extract_posting = {
    "behavior": (
        "Given one posting's payload, its source definition and a pay-floor table: returns a field record "
        "for every declared field (" + FIELD_NAMES + "), each value within its field's declared value space "
        "or null, each carrying the evidence it was derived from, " + MAPPING + "; " + SALARY_RULE + "; the "
        "result depends only on these inputs."
    ),
    "inputs": [PAYLOAD, SOURCE, PAY_FLOORS],
    "outputs": [{"name": "fields", "type": "a map from declared field name to field record", "description": FIELDS}],
}

read_stated_text = {
    "behavior": (
        "Given a payload and its source definition: returns field records for title, link, company, "
        "location, department_team and full_text. company's value is the definition's company, with one "
        "evidence entry {path: 'source.company', span: null, raw: the company, value: the company}. For each "
        "other field, the locators the definition lists for it are read in order; every non-empty text found "
        "at a locator's path (each element, for a path stepping into a list) is converted by the locator's "
        "format and contributes one evidence entry {path: the element's indexed path, span: null, raw: the "
        "board's value, value: the converted text}, a converted text that is empty or repeats an earlier one "
        "for the same field contributing nothing. Conversion: 'plain' text is kept with whitespace runs "
        "collapsed to one space and the ends trimmed; 'html' has its tags removed, block-level boundaries "
        "(paragraphs, list items, line breaks, headings) becoming line breaks, its entities decoded, and "
        "other whitespace runs collapsed; 'escaped_html' is entity-decoded once and then converted as html. "
        "title's and link's value is the first contributed text; location's, department_team's and "
        "full_text's is the list of contributed texts in order; a field with no contribution is null with no "
        "evidence."
    ),
    "inputs": [PAYLOAD, SOURCE],
    "outputs": [
        rec("title", "The posting's title."),
        rec("link", "The posting's page address."),
        rec("company", "The employer, from the source definition."),
        rec("location", "Every location text the posting states."),
        rec("department_team", "Every department or team name the posting states."),
        rec("full_text", "The posting's text, one value per piece read."),
    ],
}

derive_geography = {
    "behavior": (
        "Given a payload, its source definition and the posting's location field record: countries holds "
        "every country named, by an entry in the leaf's country table, in the texts at the definition's "
        "countries locators (where a value may be an ISO 3166-1 alpha-2 code, a country name, or something "
        "else) and in the location texts, as whole words: a name of two or three letters (a code, or a "
        "short form such as 'USA' or 'NA') counts only in capitals, so 'us' in 'join us' is not the US, and "
        "a longer name counts in any case; a countries-locator value that is exactly a two-letter code is "
        "read as that ISO code in any case. The table pairs each country with "
        "the names and codes taken to denote it alone, and is built so that a common short form ('US', "
        "'USA', 'UK', 'UAE') is in it; a text that could also denote a US state ('Georgia', or in location "
        "text a two-letter code that is also a US state abbreviation, such as 'CA' or 'IN') is not; and a US "
        "state named in full, or by a postal abbreviation that is not also an ISO country code, implies "
        "'US'; city names are not in it. The table decides: a name it lacks gives nothing, even where a "
        "reader would recognise it, and an entry counts wherever it appears, even where the text means "
        "something else by it (a town that shares a country's name). regions holds every region the same "
        "texts name by an entry in the leaf's region table (which holds common synonyms, e.g. 'North "
        "America'/'NA'/'NAMER', 'Americas'/'AMER', 'LATAM', 'EMEA', 'Europe', 'APAC'), plus each listed "
        "country's most specific regions; a region "
        "never implies a country, and one region is never added because another names it. Each value's "
        "evidence is {path, span, raw: the matched text, value}; an implied region's evidence is the "
        "evidence of the country that implied it, with value the region. A value at a countries locator that "
        "names neither one country nor a region in the tables (e.g. 'Worldwide'; 'European Union' names the "
        "region europe) is kept as evidence with value null. Each field is null when it has no value."
    ),
    "inputs": [PAYLOAD, SOURCE, rec("location", "The posting's location texts, from read_stated_text.")],
    "outputs": [rec("countries", "Countries the posting names."), rec("regions", "Regions the posting names or its countries imply.")],
}

derive_work_arrangement = {
    "behavior": (
        "Given a payload, its source definition and the posting's location field record: the definition's "
        "work_arrangement locators are read in order, each board value found being looked up in the "
        "locator's values map; a mapped value contributes evidence with that value, an unmapped one evidence "
        "with value null. The field's value is the first mapped value in locator order. Only when no locator "
        "yields a mapped value are the location texts read: the whole word 'remote' gives 'remote', 'hybrid' "
        "gives 'hybrid', and 'on-site', 'onsite', 'in-office' or 'in office' give 'onsite' (case-insensitive, "
        "each match evidence with its span); texts naming more than one arrangement give null, with every "
        "match kept as evidence. Absence of any such word gives null, never 'onsite'."
    ),
    "inputs": [PAYLOAD, SOURCE, rec("location", "The posting's location texts, from read_stated_text.")],
    "outputs": [rec("work_arrangement", "The posting's work arrangement.")],
}

derive_employment_type = {
    "behavior": (
        "Given a payload, its source definition and the posting's title field record: the definition's "
        "employment_type locators are read in order, each board value found being looked up in the "
        "locator's values map; a mapped value contributes evidence with that value, an unmapped one evidence "
        "with value null. The field's value is the first mapped value in locator order. Only when no locator "
        "yields a mapped value is the title read, through the leaf's employment-type table (case-insensitive, "
        "whole words): 'Intern', 'Interns' and 'Internship' give 'internship', 'Contractor' gives 'contract', "
        "'Part-time' and 'Part Time' give 'part-time', 'Temporary' gives 'temporary', 'Full-time' and 'Full "
        "Time' give 'full-time'; 'Contract' counts only when set off from the role, in brackets or after a "
        "separator at the end of the title (so 'Contracts Manager' gives nothing), and 'Temp' only in "
        "brackets; a match inside one of the table's exception phrases, in which the word names the work "
        "rather than its terms ('Internship Program', 'Full-Time Equivalent'), gives nothing. Each match is "
        "evidence with its span. The table decides: a word it lacks gives nothing, and a listed word in a "
        "phrase its exceptions lack counts ('Intern Coordinator' gives 'internship'). A title naming more "
        "than one type gives null with every match kept as evidence; no match gives null."
    ),
    "inputs": [PAYLOAD, SOURCE, rec("title", "The posting's title, from read_stated_text.")],
    "outputs": [rec("employment_type", "The posting's employment type.")],
}

derive_seniority = {
    "behavior": (
        "Given the posting's title field record: the value is every level named in the title by a word or "
        "phrase in the leaf's level table (case-insensitive, whole words; the table includes 'Senior' and "
        "'Sr.' for 'senior', 'Staff' for 'staff', 'Principal' for 'principal', 'Director' for 'director', "
        "'Vice President' and 'VP' for 'executive', 'Intern' for 'intern'), as a sorted list of distinct "
        "levels; a match inside one of the table's exception phrases, in which a level word is not a level "
        "('Chief of Staff', 'Lead Generation'), gives nothing. The table decides: a word it lacks gives "
        "nothing, and a level word in a phrase its exceptions lack counts as that level ('Staff Pharmacist' "
        "gives 'staff'). Each match is evidence {path: the title's path, span, raw: the matched text, value: "
        "the level}. No match gives null."
    ),
    "inputs": [rec("title", "The posting's title, from read_stated_text.")],
    "outputs": [rec("seniority", "The levels the posting's title names.")],
}

derive_salary = {
    "behavior": (
        "Given the posting's full_text and countries field records and a pay-floor table: a salary statement "
        "is a range of two figures with a currency given as a symbol or an ISO 4217 code (e.g. '$139,200 — "
        "$235,200 USD', 'USD 90,000 - 120,000', '€50k–€60k'), the figures separated by a dash or 'to', a "
        "trailing 'k' multiplying by 1,000; single figures are not salary statements. Currency: an ISO code "
        "stated with the figures; otherwise '€' is EUR and '£' is GBP; a bare '$' is USD only when the "
        "countries value is exactly ['US'], and otherwise the currency is null. Pay period: as stated beside "
        "the figures ('per hour', 'hourly', '/hr' -> 'hour'; 'per day', 'daily' -> 'day'; 'per week', "
        "'weekly' -> 'week'; 'per month', 'monthly' -> 'month'; 'per year', 'annually', 'annual', 'yearly', "
        "'per annum', '/yr' -> 'year'); when none is stated, 'year' if the currency is non-null, has an entry "
        "in the pay-floor table, and the lower figure is at least that entry; otherwise null. When the text "
        "makes one salary statement the value is {minimum, maximum, currency, pay_period}; when it makes "
        "several that agree on currency and pay period, the value spans their lowest minimum and highest "
        "maximum; when they disagree, or there are none, the value is null. Every statement found is "
        "evidence {path: the full_text piece's path, span, raw: the matched text, value: that statement's "
        "salary}."
    ),
    "inputs": [
        rec("full_text", "The posting's text, one value per piece, from read_stated_text."),
        rec("countries", "The posting's countries, from derive_geography."),
        PAY_FLOORS,
    ],
    "outputs": [rec("salary", "The posting's salary as stated.")],
}

derive_years_of_experience = {
    "behavior": (
        "Given the posting's full_text field record: a requirement statement is text in one of these forms "
        "(case-insensitive), with N one or two digits or an English number word up to twenty, and 'years' "
        "also written 'year', 'yrs' or 'yr': 'N+ years'; 'N-M years' or 'N to M years', with any dash "
        "(minimum N); 'at least N years'; 'minimum N years', with 'a' and 'of' optional ('a minimum of N "
        "years'); 'N or more years'; 'N years experience' or \"N years' experience\"; or 'N years of' followed "
        "by up to four words and then 'experience'. The value is the lowest N across all requirement "
        "statements in the text, or null when there are none. The forms decide: a mention of years in none "
        "of them is not one ('after 4 years', 'every 2 years', 'founded 10 years ago', 'in 2 years you will "
        "gain experience'), and a mention in one of them counts even when it states no requirement ('fully "
        "remote for at least 3 years' gives 3). Every requirement statement found is evidence {path: the "
        "piece's path, span, raw: the matched text, value: its N}."
    ),
    "inputs": [rec("full_text", "The posting's text, one value per piece, from read_stated_text.")],
    "outputs": [rec("years_of_experience", "The lowest number of years of experience the posting requires.")],
}

read_posted_date = {
    "behavior": (
        "Given a payload and its source definition: when the definition's date is non-null and the value at "
        "its path parses in its format ('iso8601': the calendar date as written, in the timestamp's own "
        "offset; 'epoch_millis': the UTC calendar date), the value is that date as 'YYYY-MM-DD', with evidence "
        "{path, span: null, raw: the board's value, value: the date}. When the definition's date is null, the "
        "path holds nothing, or the value does not parse, the value is null (undated), the board's value "
        "being kept as evidence with value null when there was one."
    ),
    "inputs": [PAYLOAD, SOURCE],
    "outputs": [rec("posted_date", "The posting's own date.")],
}

merge_into_store = {
    "behavior": (
        "Given the stored postings, extracted results for some sources, and the current date: for each 'ok' "
        "result, every posting it lists is in the returned store under (source_id, posting_id) with the "
        "payload and fields just extracted, a posting not previously stored taking first_seen = as_of and "
        "one previously stored keeping its first_seen, and both being listed (since null); every previously "
        "stored posting of that source absent from the result is no_longer_listed, keeping its since date if "
        "it already was and taking as_of if not. Entries of sources with a 'failed' result, or with no "
        "result, are returned unchanged. No entry is removed, and the store is sorted by source_id then "
        "posting_id. The report has one record per result, in the same order: for 'ok', listed (postings in "
        "the result), new (not previously stored), no_longer_listed (became no longer listed in this run) and "
        "listed_again (were no longer listed and are listed now); for 'failed', the reason."
    ),
    "inputs": [
        STORE_IN,
        {"name": "extracted_results", "type": "a list of extracted results with distinct source_ids", "description": EXTRACTED_RESULT_DESC},
        AS_OF,
    ],
    "outputs": refresh_root["outputs"],
}

refresh_tree = {
    "id": "n1",
    "contract": refresh_root,
    "assembly_pattern": "sequential",
    "glue": (
        "fetch_results = fetch_sources(sources)\n"
        "extracted_results = extract_fetched(fetch_results, sources, pay_floors)\n"
        "return merge_into_store(stored_postings, extracted_results, as_of)\n"
    ),
    "children": [
        {"name": "fetch_sources", "id": "n2", "contract": fetch_sources, "assembly_pattern": "iterative",
         "glue": "return [fetch_source(source) for source in sources]\n",
         "children": [{"name": "fetch_source", "id": "n5", "contract": fetch_source}]},
        {"name": "extract_fetched", "id": "n3", "contract": extract_fetched, "assembly_pattern": "iterative",
         "glue": (
             "source_by_id = {source[\"id\"]: source for source in sources}\n"
             "extracted_results = []\n"
             "for result in fetch_results:\n"
             "    if result[\"status\"] != \"ok\":\n"
             "        extracted_results.append(result)\n"
             "        continue\n"
             "    source = source_by_id[result[\"source_id\"]]\n"
             "    postings = [\n"
             "        {**posting, \"fields\": extract_posting(posting[\"payload\"], source, pay_floors)}\n"
             "        for posting in result[\"postings\"]\n"
             "    ]\n"
             "    extracted_results.append({**result, \"postings\": postings})\n"
             "return extracted_results\n"
         ),
         "children": [
             {"name": "extract_posting", "id": "n6", "contract": extract_posting, "assembly_pattern": "sequential",
              "glue": (
                  "stated = read_stated_text(payload, source)\n"
                  "geography = derive_geography(payload, source, stated[\"location\"])\n"
                  "return {\n"
                  "    **stated,\n"
                  "    **geography,\n"
                  "    \"work_arrangement\": derive_work_arrangement(payload, source, stated[\"location\"]),\n"
                  "    \"employment_type\": derive_employment_type(payload, source, stated[\"title\"]),\n"
                  "    \"seniority\": derive_seniority(stated[\"title\"]),\n"
                  "    \"salary\": derive_salary(stated[\"full_text\"], geography[\"countries\"], pay_floors),\n"
                  "    \"years_of_experience\": derive_years_of_experience(stated[\"full_text\"]),\n"
                  "    \"posted_date\": read_posted_date(payload, source),\n"
                  "}\n"
              ),
              "children": [
                  {"name": "read_stated_text", "id": "n7", "contract": read_stated_text},
                  {"name": "derive_geography", "id": "n8", "contract": derive_geography},
                  {"name": "derive_work_arrangement", "id": "n9", "contract": derive_work_arrangement},
                  {"name": "derive_employment_type", "id": "n10", "contract": derive_employment_type},
                  {"name": "derive_seniority", "id": "n11", "contract": derive_seniority},
                  {"name": "derive_salary", "id": "n12", "contract": derive_salary},
                  {"name": "derive_years_of_experience", "id": "n13", "contract": derive_years_of_experience},
                  {"name": "read_posted_date", "id": "n14", "contract": read_posted_date},
              ]},
         ]},
        {"name": "merge_into_store", "id": "n4", "contract": merge_into_store},
    ],
}

# ---------------------------------------------------------------- assess

RULE_DESC = (
    "A rule is {id, field, test, action, unknowns} plus the test's parameters. Tests: 'contains' with "
    "keywords (a non-empty list of words or phrases), on field 'title' or 'full_text'; 'one_of' with values "
    "(a non-empty list from the field's value space), on 'company', 'department_team', 'countries', "
    "'regions', 'work_arrangement', 'employment_type', 'seniority' or 'listing_status' (values 'listed', "
    "'no_longer_listed'); 'at_least' or 'at_most' with amount (a number), on 'years_of_experience', or on "
    "'salary' with currency (ISO 4217) and pay_period as well; 'within_days' with days (a non-negative "
    "integer), on 'posted_date' or 'first_seen'. action is 'require', 'exclude' or 'prefer'. unknowns is "
    "'show' or 'hide' and applies to require and exclude rules only, defaulting to 'show'."
)
VERDICT_DESC = (
    "A verdict is {rule_id, result, field, value, evidence}: result 'met', 'not_met' or 'cant_tell'; field "
    "the rule's field; value the posting's value for that field (null when unknown); evidence the entries "
    "the result rests on: for a contains test that is met, one entry per match {path: the piece's path, "
    "span, raw: the matched text, value: the keyword}; for first_seen and listing_status, one entry with path "
    "'entry.first_seen' or 'entry.listing'; otherwise the tested field record's evidence."
)
VERDICTS_DESC = (
    "One item per posting, in the order of the postings: {source_id, posting_id, verdicts}, verdicts one "
    "per rule in rule order. " + VERDICT_DESC
)
MARKS_DESC = (
    "For each posting the user has marked: {source_id, posting_id, marks}, at most one item per posting, "
    "marks a non-empty list from 'viewed', 'saved', 'applied', 'hidden' ('hidden' meaning hidden by you). "
    "Belongs to this user alone."
)
RECORD_DESC = (
    "An assessment record is {source_id, posting_id, fields, first_seen, listing, verdicts, prefer_met, "
    "marks, flags}: fields, first_seen and listing as stored; verdicts one per rule in rule order; "
    "prefer_met the number of prefer rules whose verdict is met; marks the user's marks for the posting in "
    "the order viewed, saved, applied, hidden (empty when unmarked); flags {new, no_longer_listed, "
    "no_posting_date}: new when not marked viewed, no_longer_listed when the listing status is "
    "no_longer_listed, no_posting_date when posted_date is null. " + VERDICT_DESC
)
REASONS_DESC = (
    "A hidden record also carries reasons, a non-empty list: {kind: 'hidden_by_you'} first when marked "
    "hidden, then, in rule order, {kind: 'failed', rule_id} or {kind: 'couldnt_check', rule_id}."
)
SHOWN_DESC = (
    "One record per shown posting, ordered by prefer_met (most first), then posted_date, or first_seen when "
    "posted_date is null (newest first), then source_id and posting_id. " + RECORD_DESC
)
HIDDEN_DESC = "One record per hidden posting, ordered by source_id then posting_id. " + RECORD_DESC + " " + REASONS_DESC
DIAG_DESC = (
    "One record per rule, in rule order: {rule_id, met, not_met, cant_tell, hid, hid_couldnt_check, "
    "could_not_check}: counts of each verdict over the watched postings; hid, the number of hidden postings "
    "the rule is a reason for, and hid_couldnt_check, how many of those for couldnt_check; could_not_check, "
    "the {source_id, posting_id} of every posting whose verdict was cant_tell, ordered by source_id then "
    "posting_id. The material the user refines their rules with."
)
RULES_IN = {"name": "rules", "type": "a list of rules with distinct ids, possibly empty",
            "description": "The user's editable statement of what they want to see, refined between runs. " + RULE_DESC}

ASSESS_BEHAVIOR = json.load(open(os.path.join(RUN, "root-contract-assess.json")))["behavior"]

assess_root = {
    "behavior": ASSESS_BEHAVIOR,
    "inputs": [
        STORE_IN,
        {"name": "watched_sources", "type": "a list of distinct source ids",
         "description": "The sources this user follows. Postings from other sources are outside this assessment."},
        RULES_IN,
        {"name": "marks", "type": "a list of per-posting mark records", "description": MARKS_DESC},
        AS_OF,
    ],
    "outputs": [
        {"name": "shown", "type": "an ordered list of assessment records", "description": SHOWN_DESC},
        {"name": "hidden", "type": "an ordered list of assessment records with reasons", "description": HIDDEN_DESC},
        {"name": "rule_diagnostics", "type": "a list of per-rule records", "description": DIAG_DESC},
    ],
}

POSTINGS_IN = {"name": "postings", "type": "a list of stored-posting entries", "description": STORE_DESC}
VERDICTS_IN = {"name": "verdicts", "type": "a list of per-posting verdict lists", "description": VERDICTS_DESC}

# What a verdict is: stated once, carried by evaluate_rules and evaluate_rule alike.
VERDICT_RULES = (
        "The tested value is the posting's field value (first_seen and listing status come from the entry "
        "itself). The verdict is cant_tell when the value is null, or when a salary's currency or pay_period "
        "is null or differs from the rule's. Otherwise, by test: "
        "contains is met when any keyword occurs in the title, or in any piece of full_text, "
        "case-insensitively, as a whole word or whole phrase, bounded by characters that are not letters or "
        "digits; whitespace in a phrase matches any run of whitespace; a keyword ending in '*' matches any "
        "continuation of letters or digits. "
        "one_of on company, work_arrangement, employment_type or listing_status is met when the value is one "
        "of the rule's values; on department_team, whose values describe the posting together, it is met "
        "when any value is one of the rule's values. Text values are compared ignoring case and surrounding "
        "whitespace. "
        "at_least and at_most compare years_of_experience with amount, inclusively. "
        "within_days is met when the date is on or after the current date minus days. "
        "These results are the same for every action. Countries, regions, seniority and a salary's range "
        "hold alternatives, and each value is judged on its own: a country or seniority level meets a one_of "
        "rule when it is one of the rule's values and fails otherwise; a region meets it when it or a region "
        "containing it is one of the rule's values, cannot be told when one of the rule's values lies "
        "strictly inside it, and fails otherwise; every amount from minimum to maximum is a value of a salary "
        "range, judged against amount inclusively. Over alternatives, a require or prefer rule is met when any "
        "value meets it, otherwise cant_tell when any value cannot be told, otherwise not_met; an exclude rule "
        "is met when every value meets it, not_met when any value fails, otherwise cant_tell. The verdict "
        "names the field, the value and the evidence it rests on. "
        + REGIONS
)

evaluate_rules = {
    "behavior": (
        "Given postings, rules and the current date: returns one item per posting, in the same order, naming "
        "the posting and holding one verdict per rule in rule order, each the verdict of that rule on that "
        "posting at the current date, as follows. "
        + VERDICT_RULES
    ),
    "inputs": [POSTINGS_IN, RULES_IN, AS_OF],
    "outputs": [{"name": "verdicts", "type": "a list of per-posting verdict lists", "description": VERDICTS_DESC}],
}

evaluate_rule = {
    "behavior": (
        "Given one stored posting, one rule and the current date, returns the rule's verdict on the posting. "
        + VERDICT_RULES
    ),
    "inputs": [
        {"name": "posting", "type": "a stored-posting entry", "description": STORE_DESC},
        {"name": "rule", "type": "a rule", "description": RULE_DESC},
        AS_OF,
    ],
    "outputs": [{"name": "verdict", "type": "a verdict", "description": VERDICT_DESC}],
}

place_postings = {
    "behavior": (
        "Given postings, rules, every posting's verdicts and the user's marks: each posting yields exactly "
        "one assessment record, in shown or in hidden. Its reasons are 'hidden_by_you' when it is marked "
        "hidden, and, only when it is not marked saved, for each rule in order: 'failed' when a require rule "
        "is not_met or an exclude rule is met, 'couldnt_check' when a require or exclude rule whose unknowns "
        "is 'hide' is cant_tell. A posting with any reason is hidden, carrying all of them in that order; any "
        "other is shown. prefer_met counts the prefer rules that are met; a prefer rule never hides. Shown is "
        "ordered by prefer_met, most first, then by posted_date (first_seen when posted_date is null), newest "
        "first, then by source_id and posting_id; hidden by source_id then posting_id."
    ),
    "inputs": [POSTINGS_IN, RULES_IN, VERDICTS_IN, {"name": "marks", "type": "a list of per-posting mark records", "description": MARKS_DESC}],
    "outputs": [
        {"name": "shown", "type": "an ordered list of assessment records", "description": SHOWN_DESC},
        {"name": "hidden", "type": "an ordered list of assessment records with reasons", "description": HIDDEN_DESC},
    ],
}

diagnose_rules = {
    "behavior": (
        "Given the rules, every watched posting's verdicts and the hidden records: returns one record per "
        "rule in rule order, counting that rule's met, not_met and cant_tell verdicts over all the postings, "
        "the hidden records whose reasons name the rule (hid) and how many of those name it as couldnt_check "
        "(hid_couldnt_check), and listing every posting whose verdict for the rule was cant_tell."
    ),
    "inputs": [
        RULES_IN,
        VERDICTS_IN,
        {"name": "hidden", "type": "an ordered list of assessment records with reasons", "description": HIDDEN_DESC},
    ],
    "outputs": [{"name": "rule_diagnostics", "type": "a list of per-rule records", "description": DIAG_DESC}],
}

assess_tree = {
    "id": "n1",
    "contract": assess_root,
    "assembly_pattern": "sequential",
    "glue": (
        "watched = set(watched_sources)\n"
        "postings = [entry for entry in stored_postings if entry[\"source_id\"] in watched]\n"
        "verdicts = evaluate_rules(postings, rules, as_of)\n"
        "placed = place_postings(postings, rules, verdicts, marks)\n"
        "rule_diagnostics = diagnose_rules(rules, verdicts, placed[\"hidden\"])\n"
        "return {\"shown\": placed[\"shown\"], \"hidden\": placed[\"hidden\"], \"rule_diagnostics\": rule_diagnostics}\n"
    ),
    "children": [
        {"name": "evaluate_rules", "id": "n2", "contract": evaluate_rules, "assembly_pattern": "iterative",
         "glue": (
             "return [\n"
             "    {\n"
             "        \"source_id\": entry[\"source_id\"],\n"
             "        \"posting_id\": entry[\"posting_id\"],\n"
             "        \"verdicts\": [evaluate_rule(entry, rule, as_of) for rule in rules],\n"
             "    }\n"
             "    for entry in postings\n"
             "]\n"
         ),
         "children": [{"name": "evaluate_rule", "id": "n5", "contract": evaluate_rule}]},
        {"name": "place_postings", "id": "n3", "contract": place_postings},
        {"name": "diagnose_rules", "id": "n4", "contract": diagnose_rules},
    ],
}


# ---------------------------------------------------------------- checks

def walk(node, depth=1):
    yield node, depth
    for child in node.get("children", []):
        yield from walk(child, depth + 1)


def check(tree):
    for node, _ in walk(tree):
        if "glue" not in node:
            continue
        params = [i["name"] for i in node["contract"]["inputs"]]
        source = "def _glue(" + ", ".join(params) + "):\n" + "".join("    " + l + "\n" for l in node["glue"].splitlines())
        module = ast.parse(source)
        called = {n.func.id for n in ast.walk(module) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        children = {c["name"] for c in node["children"]}
        assert children <= called, (node["id"], children - called)
        for child in node["children"]:
            calls = [n for n in ast.walk(module) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == child["name"]]
            arity = len(child["contract"]["inputs"])
            assert all(len(c.args) == arity for c in calls), (child["id"], arity)
    store = [i for n, _ in walk(tree) for i in n["contract"]["inputs"] + n["contract"]["outputs"] if i["description"].endswith(STORE_DESC)]
    return store


for name, tree in [("node-tree-refresh.json", refresh_tree), ("node-tree-assess.json", assess_tree)]:
    check(tree)
    nodes = list(walk(tree))
    leaves = [n for n, _ in nodes if "children" not in n]
    print(name, "nodes", len(nodes), "leaves", len(leaves), "depth", max(d for _, d in nodes))
    with open(os.path.join(RUN, name), "w") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
        f.write("\n")

r_store = next(i for i in refresh_root["inputs"] if i["name"] == "stored_postings")
a_store = next(i for i in assess_root["inputs"] if i["name"] == "stored_postings")
assert r_store == a_store
assert refresh_root["outputs"][0]["type"] == a_store["type"]
assert refresh_root["outputs"][0]["description"].endswith(a_store["description"])
print("stored-postings interface identical across both trees")
