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
