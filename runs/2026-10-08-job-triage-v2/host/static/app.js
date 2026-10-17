"use strict";
// The job-triage page. It shows what assess returned and sends the signed-in user's changes back; it never
// filters or ranks postings itself.

const FIELD_LABELS = {
  title: "Title", full_text: "Full text", company: "Company", department_team: "Department/team",
  countries: "Country", regions: "Region", work_arrangement: "Work arrangement", employment_type: "Employment type",
  seniority: "Seniority", listing_status: "Listing status", salary: "Salary",
  years_of_experience: "Years of experience", posted_date: "Posted date", first_seen: "First seen",
};
const FIELD_GROUPS = [
  ["Text", ["title", "full_text"]],
  ["Categories", ["company", "department_team", "countries", "regions", "work_arrangement", "employment_type",
    "seniority", "listing_status"]],
  ["Numbers", ["salary", "years_of_experience"]],
  ["Dates", ["posted_date", "first_seen"]],
];
const TESTS = {
  title: ["contains"], full_text: ["contains"], salary: ["at_least", "at_most"],
  years_of_experience: ["at_least", "at_most"], posted_date: ["within_days"], first_seen: ["within_days"],
};
const testsFor = (field) => TESTS[field] || ["one_of"];
const TEST_LABELS = { contains: "contains", one_of: "is one of", at_least: "at least", at_most: "at most",
  within_days: "within the last" };
const OPEN_FIELDS = new Set(["company", "department_team", "countries"]);
const VALUE_LABELS = {
  regions: { north_america: "North America", latin_america: "Latin America", americas: "Americas", europe: "Europe",
    middle_east: "Middle East", africa: "Africa", emea: "EMEA", asia: "Asia", oceania: "Oceania", apac: "APAC" },
  work_arrangement: { remote: "Remote", hybrid: "Hybrid", onsite: "On-site" },
  employment_type: { "full-time": "Full-time", "part-time": "Part-time", contract: "Contract",
    temporary: "Temporary", internship: "Internship" },
  seniority: { intern: "Intern", junior: "Junior", senior: "Senior", staff: "Staff", principal: "Principal",
    lead: "Lead", manager: "Manager", director: "Director", executive: "Executive" },
  listing_status: { listed: "Listed", no_longer_listed: "No longer listed" },
};
const ACTIONS = {
  require: ["Require", "Hide postings that don't meet it"],
  exclude: ["Exclude", "Hide postings that meet it"],
  prefer: ["Prefer", "Rank postings that meet it higher; never hides anything"],
};
const RESULTS = { met: "met", not_met: "not met", cant_tell: "can't tell" };
// A verdict's colour and icon say what it does to the posting: an exclude rule not met counts for it.
const EFFECT_ICONS = { for: "✓", against: "✗", unknown: "?", neutral: "–" };

function effect(rule, result) {
  if (result === "cant_tell") return "unknown";
  if (!rule) return "neutral";
  if (rule.action === "exclude") return result === "met" ? "against" : "for";
  if (rule.action === "prefer") return result === "met" ? "for" : "neutral";
  return result === "met" ? "for" : "against";
}

let state = null;
const ui = { tab: "shown", expanded: new Set(), refreshing: false, showReport: false };

let regionNames = null;
try { regionNames = new Intl.DisplayNames(["en"], { type: "region" }); } catch { /* names are a nicety */ }

// --- helpers ---

const $ = (selector) => document.querySelector(selector);

function h(tag, props, ...children) {
  const el = document.createElement(tag);
  const late = {};
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (["value", "checked", "disabled", "selected"].includes(key)) late[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  Object.assign(el, late);
  return el;
}

const number = (n) => Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 });

function countryName(code) {
  try {
    const name = regionNames && regionNames.of(code);
    return name && name !== code ? `${name} (${code})` : code;
  } catch { return code; }
}

function valueLabel(field, value) {
  if (field === "countries") return countryName(value);
  return (VALUE_LABELS[field] || {})[value] || value;
}

function formatSalary(s) {
  if (!s) return null;
  const range = s.minimum === s.maximum ? number(s.minimum) : `${number(s.minimum)}–${number(s.maximum)}`;
  return `${s.currency || "?"} ${range}${s.pay_period ? ` / ${s.pay_period}` : " (pay period unknown)"}`;
}

function formatValue(field, value) {
  if (value === null || value === undefined) return "unknown";
  if (field === "salary") return formatSalary(value);
  if (Array.isArray(value)) return value.map((v) => valueLabel(field, v)).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(valueLabel(field, value));
}

function ruleText(rule) {
  const field = FIELD_LABELS[rule.field];
  switch (rule.test) {
    case "contains": return `${field} contains ${rule.keywords.map((k) => `“${k}”`).join(" or ")}`;
    case "one_of": return `${field} is ${rule.values.map((v) => valueLabel(rule.field, v)).join(" or ")}`;
    case "at_least":
    case "at_most": {
      const unit = rule.field === "salary" ? ` ${rule.currency} per ${rule.pay_period}` : " years";
      return `${field} ${TEST_LABELS[rule.test]} ${number(rule.amount)}${unit}`;
    }
    case "within_days": return `${field} within the last ${rule.days} days`;
    default: return field;
  }
}
const ruleSentence = (rule) => (rule ? `${ACTIONS[rule.action][0]}: ${ruleText(rule)}` : "(deleted rule)");

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 4000);
}

async function api(path, body) {
  const init = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Requested-With": "job-triage" },
    body: JSON.stringify(body),
  };
  const response = await fetch(path, { credentials: "same-origin", ...init });
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (response.status === 401 && path !== "/api/login") {
    state = null;
    start();
  }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function change(path, body) {
  try {
    state = await api(path, body);
    render();
  } catch (error) {
    toast(error.message);
  }
}

function confirmDialog(title, text, confirmLabel) {
  return new Promise((resolve) => {
    const dialog = $("#dialog");
    const finish = (answer) => { dialog.close(); resolve(answer); };
    dialog.replaceChildren(
      h("h2", { text: title }),
      ...[].concat(text).map((line) => h("p", { text: line })),
      h("div", { class: "dialog-actions" },
        h("button", { type: "button", onclick: () => finish(false) }, "Cancel"),
        h("button", { type: "button", class: "primary", onclick: () => finish(true) }, confirmLabel)),
    );
    dialog.oncancel = () => resolve(false);
    dialog.showModal();
  });
}

// --- sign in ---

async function start() {
  try {
    const session = await api("/api/session");
    if (!session.user) return renderLogin(session);
    state = await api("/api/state");
    render();
  } catch (error) {
    toast(error.message);
  }
}

function renderLogin(session) {
  const error = h("p", { class: "error", role: "alert" });
  const username = h("input", { id: "username", autocomplete: "username", required: true });
  const password = h("input", { id: "password", type: "password", autocomplete: "current-password", required: true });
  async function signIn(name, secret) {
    try {
      await api("/api/login", { username: name, password: secret });
      ui.tab = "shown";
      ui.expanded.clear();
      ui.showReport = false;
      state = await api("/api/state");
      render();
    } catch (e) {
      error.textContent = e.message;
    }
  }
  $("#app").replaceChildren(h("main", { class: "login" },
    h("h1", { text: "Job triage" }),
    h("form", { onsubmit: (e) => { e.preventDefault(); signIn(username.value.trim(), password.value); } },
      h("h2", { text: "Sign in" }),
      h("label", { class: "field", for: "username" }, "Username", username),
      h("label", { class: "field", for: "password" }, "Password", password),
      h("button", { class: "primary", type: "submit" }, "Sign in"),
      error),
    session.demo_users.length ? h("section", { class: "demo" },
      h("h2", { text: "Demo accounts" }),
      h("p", { class: "hint", text: `Each one's password is “${session.demo_password}”.` }),
      session.demo_users.map((u) => h("button", { class: "demo-user", onclick: () => signIn(u.username, session.demo_password) },
        h("strong", { text: `Sign in as ${u.username}` }), u.about ? h("span", { text: u.about }) : null))) : null));
  username.focus();
}

async function switchUser() {
  try { await api("/api/logout", {}); } catch { /* signed out either way */ }
  state = null;
  start();
}

// --- the page ---

function render() {
  $("#app").replaceChildren(...[
    renderHeader(),
    ui.showReport && state.refresh ? renderReport() : null,
    h("div", { class: "layout" },
      h("aside", {}, renderAccount(), renderSources(), renderRules(), renderSettings()),
      h("main", {}, renderPostings())),
  ].filter(Boolean));
}

function renderHeader() {
  const r = state.refresh;
  return h("header", { class: "top" },
    h("div", { class: "brand" }, h("h1", { text: "Job triage" }), h("span", { class: "muted", text: `as of ${state.as_of}` })),
    h("div", { class: "refresh" },
      h("span", { class: "muted", text: `${number(state.stored)} postings stored · ${r ? `refreshed ${r.as_of}` : "never refreshed"}` }),
      h("button", { onclick: refresh, disabled: ui.refreshing }, ui.refreshing ? "Refreshing…" : "Refresh postings")),
    h("div", { class: "who" },
      h("span", { class: "user-chip", text: state.user.username }),
      h("button", { class: "link", onclick: switchUser }, "Switch user")));
}

async function refresh() {
  ui.refreshing = true;
  render();
  try {
    state = await api("/api/refresh", {});
    ui.showReport = true;
  } catch (error) {
    toast(error.message);
  } finally {
    ui.refreshing = false;
    if (state) render();
  }
}

function renderReport() {
  const companies = Object.fromEntries(state.sources.map((s) => [s.id, s.company]));
  return h("div", { class: "report", role: "status" },
    h("strong", { text: `Refresh ${state.refresh.as_of}` }),
    state.refresh.source_report.map((s) => s.status === "ok"
      ? h("span", { text: `${companies[s.source_id] || s.source_id}: ${s.listed} listed, ${s.new} new, ${s.no_longer_listed} no longer listed, ${s.listed_again} listed again` })
      : h("span", { class: "failed", text: `${companies[s.source_id] || s.source_id}: failed (${s.reason}); its stored postings are unchanged` })),
    h("button", { class: "link", onclick: () => { ui.showReport = false; render(); } }, "Dismiss"));
}

function renderAccount() {
  return h("section", { class: "panel" },
    h("h2", { text: `Signed in as ${state.user.username}` }),
    state.user.about ? h("p", { class: "muted", text: state.user.about }) : null);
}

function renderSources() {
  const watched = new Set(state.user.watched_sources);
  const toggle = (id, on) => change("/api/watched", {
    watched_sources: state.sources.map((s) => s.id).filter((s) => (s === id ? on : watched.has(s))),
  });
  return h("section", { class: "panel" },
    h("h2", { text: "Sources you watch" }),
    state.sources.map((s) => h("label", { class: "check" },
      h("input", { type: "checkbox", checked: watched.has(s.id), onchange: (e) => toggle(s.id, e.target.checked) }),
      h("span", {}, s.company, h("span", { class: "muted", text: ` · ${number(s.stored)} stored` })))));
}

function renderRules() {
  const diagnostics = Object.fromEntries(state.rule_diagnostics.map((d) => [d.rule_id, d]));
  const rules = state.user.rules;
  return h("section", { class: "panel" },
    h("div", { class: "panel-head" },
      h("h2", { text: "Rules" }),
      h("button", { class: "primary small", onclick: () => editRule(null) }, "Add rule")),
    rules.length
      ? h("ol", { class: "rules" }, rules.map((rule) => renderRule(rule, diagnostics[rule.id])))
      : h("p", { class: "muted", text: "No rules yet, so every posting from your sources is shown." }));
}

function renderRule(rule, d) {
  return h("li", { class: "rule" },
    h("div", { class: "rule-text" }, h("span", { class: `action ${rule.action}`, text: ACTIONS[rule.action][0] }), " ", ruleText(rule)),
    rule.action === "prefer" ? null : h("div", {
      class: `rule-unknowns${rule.unknowns === "hide" ? " hides" : ""}`,
      text: rule.unknowns === "hide" ? "Can't tell: hidden" : "Can't tell: shown",
    }),
    d ? h("div", { class: "diag" },
      `${d.met} met · ${d.not_met} not met · ${d.cant_tell} can't tell`,
      rule.action === "prefer" ? "" : ` · hiding ${d.hid}${d.hid_couldnt_check ? ` (${d.hid_couldnt_check} couldn't check)` : ""}`) : null,
    h("div", { class: "rule-actions" },
      h("button", { class: "link", onclick: () => editRule(rule) }, "Edit"),
      h("button", { class: "link danger", onclick: () => deleteRule(rule) }, "Delete")));
}

async function deleteRule(rule) {
  if (await confirmDialog("Delete this rule?", ruleSentence(rule), "Delete")) {
    change("/api/rules", { rules: state.user.rules.filter((r) => r.id !== rule.id) });
  }
}

function renderSettings() {
  return h("section", { class: "panel" },
    h("h2", { text: "Defaults" }),
    h("p", { class: "muted", text: "Restoring defaults sets every rule's “can't tell” back to shown. Your rules, sources and marks stay as they are." }),
    h("div", { class: "row" },
      h("button", { onclick: restoreDefaults }, "Restore defaults…"),
      state.user.can_undo_restore ? h("button", { onclick: () => change("/api/undo-restore", {}) }, "Undo restore") : null));
}

async function restoreDefaults() {
  const hiding = state.user.rules.filter((r) => r.unknowns === "hide");
  const text = hiding.length
    ? [`${hiding.length === 1 ? "1 rule hides" : `${hiding.length} rules hide`} postings it can't check. After this, every rule shows them.`,
       "Your rules, watched sources and marks stay as they are, and you can undo this."]
    : ["Every rule already shows postings it can't check, so nothing will change."];
  if (await confirmDialog("Restore defaults?", text, "Restore defaults")) change("/api/restore-defaults", {});
}

// --- postings ---

function renderPostings() {
  const list = ui.tab === "shown" ? state.shown : state.hidden;
  const tab = (name, label) => h("button", {
    role: "tab", "aria-selected": String(ui.tab === name),
    onclick: () => { ui.tab = name; render(); },
  }, label);
  return [
    h("div", { class: "tabs", role: "tablist" },
      tab("shown", `Shown (${state.shown.length})`), tab("hidden", `Hidden (${state.hidden.length})`)),
    ui.tab === "hidden" && state.hidden.length ? hiddenSummary() : null,
    list.length && state.user.rules.length
      ? h("p", { class: "summary", text: "✓ counts for the posting · ✗ counts against it · ? can't tell · – preference not met" })
      : null,
    list.length ? h("ul", { class: "cards" }, list.map(renderCard)) : h("p", { class: "empty", text: emptyText() }),
  ];
}

function emptyText() {
  if (!state.stored) return "No postings stored yet. Refresh postings to fetch them from the sources.";
  if (!state.user.watched_sources.length) return "You aren't watching any sources.";
  return ui.tab === "shown" ? "Nothing is shown: every watched posting is hidden. See Hidden for the reasons." : "Nothing is hidden.";
}

function hiddenSummary() {
  const count = (kind) => state.hidden.filter((r) => r.reasons.some((reason) => reason.kind === kind)).length;
  return h("p", { class: "summary", text: `Hidden by you: ${count("hidden_by_you")} · failed a rule: ${count("failed")} · couldn't check: ${count("couldnt_check")}. A posting can have several reasons.` });
}

function reasonText(reason, rules) {
  if (reason.kind === "hidden_by_you") return "Hidden by you";
  const label = reason.kind === "failed" ? "Failed" : "Couldn't check";
  return `${label}: ${ruleSentence(rules[reason.rule_id])}`;
}

function renderCard(record) {
  const key = `${record.source_id}|${record.posting_id}`;
  const f = record.fields;
  const marks = new Set(record.marks);
  const rules = Object.fromEntries(state.user.rules.map((r) => [r.id, r]));
  const expanded = ui.expanded.has(key);
  const prefers = state.user.rules.filter((r) => r.action === "prefer").length;
  const mark = (name, on) => change("/api/marks", { source_id: record.source_id, posting_id: record.posting_id, mark: name, on });
  const locations = f.location || [];
  const line1 = [
    f.company,
    locations.length > 3 ? `${locations.slice(0, 3).join("; ")} +${locations.length - 3} more` : locations.join("; "),
    f.work_arrangement && valueLabel("work_arrangement", f.work_arrangement),
    f.employment_type && valueLabel("employment_type", f.employment_type),
    f.seniority && formatValue("seniority", f.seniority),
  ].filter(Boolean);
  const line2 = [
    formatSalary(f.salary),
    f.years_of_experience !== null && f.years_of_experience !== undefined ? `${number(f.years_of_experience)}+ years' experience` : null,
    f.posted_date ? `Posted ${f.posted_date}` : null,
    `First seen ${record.first_seen}`,
  ].filter(Boolean);

  return h("li", { class: `card${record.flags.new ? " new" : ""}` },
    record.reasons ? h("ul", { class: "reasons" }, record.reasons.map((r) => h("li", { class: r.kind, text: reasonText(r, rules) }))) : null,
    h("div", { class: "card-top" },
      h("div", { class: "flags" },
        record.flags.new ? h("span", { class: "flag new", text: "New" }) : null,
        record.flags.no_longer_listed ? h("span", { class: "flag gone", text: `No longer listed since ${record.listing.since}` }) : null,
        record.flags.no_posting_date ? h("span", { class: "flag", text: "No posting date" }) : null,
        marks.has("saved") ? h("span", { class: "flag saved", text: "Saved" }) : null,
        marks.has("applied") ? h("span", { class: "flag applied", text: "Applied" }) : null),
      prefers && !record.reasons ? h("span", { class: "prefer", text: `${record.prefer_met} of ${prefers} preferences met` }) : null),
    h("h3", {}, f.link
      ? h("a", { href: f.link, target: "_blank", rel: "noopener noreferrer", onclick: () => { if (!marks.has("viewed")) mark("viewed", true); } }, f.title || "(untitled)")
      : (f.title || "(untitled)")),
    line1.length ? h("p", { class: "meta", text: line1.join(" · ") }) : null,
    h("p", { class: "meta", text: line2.join(" · ") }),
    record.verdicts.length ? h("div", { class: "verdicts" }, record.verdicts.map((v) => {
      const rule = rules[v.rule_id];
      const e = effect(rule, v.result);
      return h("span", { class: `verdict ${e}`, title: `${ruleSentence(rule)}: ${RESULTS[v.result]}` },
        `${EFFECT_ICONS[e]} ${rule ? FIELD_LABELS[rule.field] : v.rule_id}`);
    })) : null,
    expanded ? renderEvidence(record, rules) : null,
    h("div", { class: "card-actions" },
      h("button", { class: "small", "aria-pressed": String(marks.has("saved")), onclick: () => mark("saved", !marks.has("saved")) }, marks.has("saved") ? "Saved" : "Save"),
      h("button", { class: "small", "aria-pressed": String(marks.has("applied")), onclick: () => mark("applied", !marks.has("applied")) }, marks.has("applied") ? "Applied" : "Mark applied"),
      h("button", { class: "small", onclick: () => mark("hidden", !marks.has("hidden")) }, marks.has("hidden") ? "Unhide" : "Hide"),
      h("button", { class: "small", onclick: () => mark("viewed", !marks.has("viewed")) }, marks.has("viewed") ? "Mark unviewed" : "Mark viewed"),
      record.verdicts.length ? h("button", {
        class: "link push", "aria-expanded": String(expanded),
        onclick: () => { (expanded ? ui.expanded.delete(key) : ui.expanded.add(key)); render(); },
      }, expanded ? "Hide evidence" : "Show evidence") : null));
}

function renderEvidence(record, rules) {
  return h("div", { class: "evidence" }, record.verdicts.map((v) => h("div", { class: "ev-row" },
    h("span", { class: `verdict ${effect(rules[v.rule_id], v.result)}`, text: RESULTS[v.result] }),
    h("div", {},
      h("div", { class: "ev-rule", text: ruleSentence(rules[v.rule_id]) }),
      v.field === "full_text" ? null : h("div", { class: "ev-value", text: `Value: ${formatValue(v.field, v.value)}` }),
      v.evidence.length
        ? h("ul", { class: "ev-list" }, v.evidence.map((e) => h("li", {}, h("code", { text: e.path }), ": ", evidenceText(v, e))))
        : h("p", { class: "hint", text: "The posting doesn't state this." })))));
}

function evidenceText(verdict, e) {
  if (e.context) return [e.context.before, h("mark", { text: e.context.match }), e.context.after];
  if (verdict.field === "full_text") return "searched, no match";
  return typeof e.raw === "string" ? `“${e.raw}”` : JSON.stringify(e.raw);
}

// --- the rule editor ---

function blankRule(field, action = "require") {
  const test = testsFor(field)[0];
  const rule = { field, test, action };
  if (action !== "prefer") rule.unknowns = "show";
  if (test === "contains") rule.keywords = [];
  if (test === "one_of") rule.values = [];
  if (test === "within_days") rule.days = 30;
  if (field === "salary") Object.assign(rule, { amount: "", currency: "USD", pay_period: "year" });
  if (field === "years_of_experience") rule.amount = "";
  return rule;
}

function editRule(existing) {
  const draft = existing ? structuredClone(existing) : blankRule("title");
  const dialog = $("#dialog");
  const error = h("p", { class: "error", role: "alert" });
  const body = h("div", {});
  const redraw = () => body.replaceChildren(...editorFields(draft, redraw).flat(Infinity).filter(Boolean));
  redraw();

  async function save(event) {
    event.preventDefault();
    const rule = { ...draft };
    if (rule.test === "at_least" || rule.test === "at_most") rule.amount = rule.amount === "" ? null : Number(rule.amount);
    if (rule.test === "within_days") rule.days = rule.days === "" ? null : Number(rule.days);
    const rules = existing ? state.user.rules.map((r) => (r.id === existing.id ? rule : r)) : [...state.user.rules, rule];
    try {
      state = await api("/api/rules", { rules });
      dialog.close();
      render();
    } catch (e) {
      error.textContent = e.message;
    }
  }

  dialog.oncancel = null;
  dialog.replaceChildren(h("form", { onsubmit: save },
    h("h2", { text: existing ? "Edit rule" : "Add rule" }),
    body,
    error,
    h("div", { class: "dialog-actions" },
      h("button", { type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { type: "submit", class: "primary" }, "Save rule"))));
  dialog.showModal();
}

function editorFields(draft, redraw) {
  const reset = (field, action) => {
    const fresh = blankRule(field, action);
    for (const key of Object.keys(draft)) if (key !== "id") delete draft[key];
    Object.assign(draft, fresh);
    redraw();
  };
  const tests = testsFor(draft.field);
  return [
    h("div", { class: "inline" },
      h("label", { class: "field" }, "Field",
        h("select", { value: draft.field, onchange: (e) => reset(e.target.value, draft.action) },
          FIELD_GROUPS.map(([group, fields]) => h("optgroup", { label: group },
            fields.map((field) => h("option", { value: field, text: FIELD_LABELS[field] })))))),
      tests.length > 1 ? h("label", { class: "field" }, "Test",
        h("select", { value: draft.test, onchange: (e) => { draft.test = e.target.value; } },
          tests.map((t) => h("option", { value: t, text: TEST_LABELS[t] })))) : null),
    valueFields(draft, redraw),
    h("fieldset", {},
      h("legend", { text: "Action" }),
      Object.entries(ACTIONS).map(([action, [name, help]]) => h("label", { class: "check" },
        h("input", {
          type: "radio", name: "action", value: action, checked: draft.action === action,
          onchange: () => {
            draft.action = action;
            if (action === "prefer") delete draft.unknowns;
            else draft.unknowns = draft.unknowns || "show";
            redraw();
          },
        }),
        h("span", {}, h("strong", { text: name }), ` · ${help}`)))),
    draft.action === "prefer"
      ? h("p", { class: "hint", text: "For a prefer rule, a posting it can't check counts as not met: it ranks lower and is never hidden." })
      : h("fieldset", {},
        h("legend", { text: "When the posting doesn't say (can't tell)" }),
        [["show", "Show it (default)"], ["hide", "Hide it, listed under Hidden as “couldn't check”"]].map(([value, label]) =>
          h("label", { class: "check" },
            h("input", { type: "radio", name: "unknowns", value, checked: draft.unknowns === value, onchange: () => { draft.unknowns = value; } }),
            label))),
  ];
}

function valueFields(draft, redraw) {
  const field = draft.field;
  if (draft.test === "contains") {
    return h("label", { class: "field" }, "Words or phrases, one per line",
      h("textarea", {
        value: (draft.keywords || []).join("\n"),
        oninput: (e) => { draft.keywords = e.target.value.split(/[\n,]/).map((k) => k.trim()).filter(Boolean); },
      }),
      h("span", { class: "hint", text: "Any one of them matches. Whole words, any case; a trailing * matches any ending, so engineer* matches engineers and engineering." }));
  }
  if (draft.test === "one_of") return oneOfFields(draft, redraw);
  if (draft.test === "within_days") {
    return h("label", { class: "field" }, `${FIELD_LABELS[field]} within the last … days`,
      h("input", { type: "number", min: "0", step: "1", value: draft.days, oninput: (e) => { draft.days = e.target.value; } }));
  }
  const amount = h("label", { class: "field" }, field === "salary" ? "Amount" : "Years",
    h("input", { type: "number", min: "0", step: "any", value: draft.amount, oninput: (e) => { draft.amount = e.target.value; } }));
  if (field !== "salary") return amount;
  const seen = [...new Set(["USD", ...state.options.salary.map((s) => s.currency)])];
  return [
    h("div", { class: "inline" },
      amount,
      h("label", { class: "field" }, "Currency",
        h("input", { list: "currencies", size: "5", maxlength: "3", value: draft.currency, oninput: (e) => { draft.currency = e.target.value.trim().toUpperCase(); } }),
        h("datalist", { id: "currencies" }, seen.map((c) => h("option", { value: c })))),
      h("label", { class: "field" }, "Per",
        h("select", { value: draft.pay_period, onchange: (e) => { draft.pay_period = e.target.value; } },
          state.options.pay_periods.map((p) => h("option", { value: p, text: p }))))),
    h("p", { class: "hint", text: "There's no currency conversion: a salary in another currency or pay period, or with no stated period, is “can't tell”. A range counts if any part of it meets the rule (for exclude, all of it)." }),
  ];
}

function oneOfFields(draft, redraw) {
  const field = draft.field;
  const chosen = new Set(draft.values);
  const options = [...state.options[field]];
  for (const value of draft.values) if (!options.some((o) => o.value === value)) options.push({ value, count: 0 });
  const list = h("div", { class: "options" }, options.map((o) => h("label", { class: "check", "data-search": `${o.value} ${valueLabel(field, o.value)}`.toLowerCase() },
    h("input", {
      type: "checkbox", checked: chosen.has(o.value),
      onchange: (e) => {
        if (e.target.checked) chosen.add(o.value); else chosen.delete(o.value);
        draft.values = options.map((x) => x.value).filter((v) => chosen.has(v));
      },
    }),
    h("span", {}, valueLabel(field, o.value), " ", h("span", { class: "count", text: `${o.count} stored` })))));
  const filter = options.length > 12 ? h("input", {
    type: "search", placeholder: "Filter", "aria-label": "Filter values",
    oninput: (e) => {
      const q = e.target.value.trim().toLowerCase();
      for (const label of list.children) label.hidden = q !== "" && !label.dataset.search.includes(q);
    },
  }) : null;
  const extra = h("input", {
    placeholder: field === "countries" ? "Two-letter code, e.g. NZ" : "Another value", "aria-label": "Add a value",
    onkeydown: (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } },
  });
  const add = () => {
    const value = field === "countries" ? extra.value.trim().toUpperCase() : extra.value.trim();
    if (value && !draft.values.includes(value)) draft.values = [...draft.values, value];
    redraw();
  };
  return h("div", { class: "field" },
    h("span", { text: `${FIELD_LABELS[field]} is any of` }),
    filter,
    list,
    OPEN_FIELDS.has(field) ? h("div", { class: "add-value" }, extra,
      h("button", { type: "button", onclick: add }, "Add")) : null,
    field === "regions" ? h("p", { class: "hint", text: "A country implies its region, but a region doesn't imply a country. EMEA, APAC and Americas contain the smaller regions." }) : null,
    h("p", { class: "hint", text: "Counts are over every stored posting, from any source." }));
}

start();
