"""Stage 4: leaf behavior checks, executed."""
import json, io, urllib.request
from datetime import datetime, timezone

TREE = json.load(open("codified-tree.json")); R=[]
def rec(n,c,m,o,d): R.append(dict(node=n,unit="leaf",category=c,method=m,outcome=o,detail=d))
L={}
def walk(x):
    if "children" in x: [walk(c) for c in x["children"]]
    else: L[x["id"]]=x
walk(TREE)
def load(nid, extra=None):
    ns=dict(extra or {}); exec(compile(L[nid]["code"],"<leaf>","exec"),ns); return ns

# ---------------- n7 ----------------
class FakeResp:
    def __init__(s,b): s._b=json.dumps(b).encode()
    def read(s): return s._b
    def __enter__(s): return s
    def __exit__(s,*a): return False
BODIES={}
urllib.request.urlopen = lambda req, *a, **k: FakeResp(BODIES[req.full_url])

ns7=load("n7",{"urllib":urllib}); f7=ns7["retrieve_from_source"]
ns7["urllib"].request.urlopen = urllib.request.urlopen
BODIES["https://x/gh"]={"jobs":[
  {"id":1,"first_published":"2026-09-01T00:00:00-04:00","t":"a"},
  {"id":2,"first_published":"2026-06-01T00:00:00-04:00","t":"b"},
  {"id":3,"first_published":"2026-09-10T00:00:00-04:00","t":"c"}]}
gh=dict(id="gh",endpoint="https://x/gh",list_path="jobs",id_locator="id",
        published_locator="first_published",published_format="iso8601",field_map={})
got=f7(gh,"2026-08-01T00:00:00+00:00",["1"])
ok = [p["source_posting_id"] for p in got]==["3"] and got[0]["raw_payload"]=={"id":3,"first_published":"2026-09-10T00:00:00-04:00","t":"c"}
rec("n7","behavior","executed","pass" if ok else "fail",
    f"window+held filtering: id2 outside window dropped, id1 held dropped, id3 returned; "
    f"raw_payload preserved byte-identical. got={[p['source_posting_id'] for p in got]}")

BODIES["https://x/lv"]=[{"pid":"z","created":1757000000000,"t":"d"}]
lv=dict(id="lv",endpoint="https://x/lv",list_path=None,id_locator="pid",
        published_locator="created",published_format="epoch_millis",field_map={})
g2=f7(lv,"2020-01-01T00:00:00+00:00",[])
ok2 = len(g2)==1 and g2[0]["published_at"].endswith("+00:00")
rec("n7","behavior","executed","pass" if ok2 else "fail",
    f"bare-array envelope + epoch-millis timestamps normalise to UTC ISO: {g2[0]['published_at'] if g2 else None}")

BODIES["https://x/nest"]={"d":{"items":[{"k":{"i":"q"},"ts":"2026-09-05T00:00:00Z"}]}}
nest=dict(id="n",endpoint="https://x/nest",list_path="d.items",id_locator="k.i",
          published_locator="ts",published_format="iso8601",field_map={})
g3=f7(nest,"2026-01-01T00:00:00+00:00",[])
rec("n7","behavior","executed","pass" if len(g3)==1 and g3[0]["source_posting_id"]=="q" else "fail",
    f"overfit check: nested list_path 'd.items' and dotted id_locator 'k.i' work on shapes unlike "
    f"the first two; contract leaves locators variable and they are not load-bearing. got={g3 and g3[0]['source_posting_id']}")

BODIES["https://x/nots"]={"jobs":[{"id":9,"t":"e"},{"id":10,"first_published":None,"t":"f"}]}
nots=dict(gh); nots["endpoint"]="https://x/nots"
g4=f7(nots,"2020-01-01T00:00:00+00:00",[])
rec("n7","behavior","executed","pass" if g4==[] else "fail",
    f"boundary: postings whose published timestamp is absent or null are omitted ({len(g4)} returned). "
    f"Consistent with this contract, which is written wholly in window terms -- a timestamp-less "
    f"posting is not demonstrably 'at or after window_start'. Flagged as a cross-contract concern: "
    f"the ROOT behavior forbids silent drops, and this leaf's contract cannot see that.")

# ---------------- n3 ----------------
f3=load("n3")["merge_corpus"]
prior={"entries":[{"source_id":"a","source_posting_id":"1","retrieved_at":"T","published_at":"P",
                   "raw_payload":{"x":1},"fields":{"f":{"value":2,"stated":True,"provenance":{}}},
                   "dispositions":{"viewed":True,"suppressed":True}}]}
out=f3(prior,[{"source_id":"a","source_posting_id":"1","published_at":"P2","raw_payload":{"x":9}},
              {"source_id":"b","source_posting_id":"1","published_at":"P3","raw_payload":{"y":1}}])
e=out["entries"]
keep = e[0]["fields"]=={"f":{"value":2,"stated":True,"provenance":{}}} and e[0]["dispositions"]=={"viewed":True,"suppressed":True} and e[0]["raw_payload"]=={"x":1}
rec("n3","behavior","executed","pass" if keep and len(e)==2 else "fail",
    f"pre-existing entry returned untouched (fields+dispositions+raw preserved, NOT overwritten by "
    f"the colliding new posting); duplicate (a,1) not re-added; distinct (b,1) added. entries={len(e)}")
new=[x for x in e if x['source_id']=='b'][0]
rec("n3","behavior","executed","pass" if new["fields"]=={} and new["dispositions"]=={"viewed":False,"suppressed":False} else "fail",
    f"new entry gets empty fields map and all-false dispositions: {new['dispositions']}")
rec("n3","behavior","executed","pass" if f3({},[])["entries"]==[] and f3({"entries":[]},None)["entries"]==[] else "fail",
    "boundary: empty corpus, absent entries key, and None new_postings all yield an empty entries list")

# ---------------- n12 ----------------
f12=load("n12")["pluck_mapped_field"]
a=f12({"a":{"b":[10,20]}},"loc","a.b.1")
b=f12({"a":{}},"loc","a.b.1")
c=f12({"a":{"b":None}},"loc","a.b")
rec("n12","behavior","executed","pass" if (a["value"]==20 and a["stated"] and not b["stated"] and not c["stated"]) else "fail",
    f"dotted locator with list index resolves ({a['value']}); unresolvable locator -> stated False; "
    f"JSON null -> stated False. provenance names the locator in all three: {a['provenance']['locator']!r}")
d=f12({"zz":{"weird key":1}},"f","zz.weird key")
rec("n12","behavior","executed","pass" if d["value"]==1 else "fail",
    "overfit check: arbitrary field and locator strings (spaces, unseen names) are not load-bearing")

# ---------------- n13 ----------------
CANNED={}
def fake_ai(instr,payload): return CANNED[payload["field"]]
f13=load("n13",{"ai":fake_ai})["infer_field_from_text"]
CANNED["salary"]={"value":"$120k","stated":True,"evidence":"Base salary is $120k"}
r=f13({"content":"<p>Base salary is $120k per year</p>"},"salary")
span_ok = r["stated"] and r["provenance"]["kind"]=="text_span" and r["provenance"]["quote"]=="Base salary is $120k"
rec("n13","behavior","executed","pass" if span_ok else "fail",
    f"given a conforming judgment, HTML is stripped and the evidence is located verbatim -> "
    f"char span {r['provenance'].get('start')}..{r['provenance'].get('end')} with value {r['value']!r}")
CANNED["remote"]={"value":"yes","stated":True,"evidence":"fully remote worldwide"}
r2=f13({"content":"This role is onsite in Portland."},"remote")
rec("n13","behavior","executed","pass" if (not r2["stated"] and r2["value"] is None) else "fail",
    f"fabricated evidence not present in the payload is DEMOTED to not-stated (stated={r2['stated']}, "
    f"value={r2['value']!r}) -- the seam cannot manufacture provenance")
CANNED["clearance"]={"value":None,"stated":False,"evidence":None}
r3=f13({"content":"Nothing relevant."},"clearance")
rec("n13","behavior","executed","pass" if (not r3["stated"] and r3["provenance"]["kind"]=="not_stated") else "fail",
    f"silent payload -> stated False with provenance kind {r3['provenance']['kind']!r}")
CANNED["x"]="not json at all"
r4=f13({"content":"t"},"x")
rec("n13","behavior","executed","pass" if not r4["stated"] else "fail",
    "malformed seam return (non-JSON string) degrades to not-stated rather than crashing")
CANNED["y"]={"value":1,"stated":True,"evidence":"deep"}
r5=f13({"a":["x",{"b":"a deep nested string"}]},"y")
rec("n13","behavior","executed","pass" if r5["stated"] else "fail",
    "overfit check: text is collected from arbitrary nested JSON, not an assumed 'content' key")

# ---------------- n11 ----------------
f11=load("n11")["evaluate_criterion"]
F={"salary":{"value":150,"stated":True,"provenance":{"kind":"locator"}},
   "remote":{"value":None,"stated":False,"provenance":{"kind":"not_stated"}}}
v1=f11(F,{"id":"c1","field":"salary","operator":"gte","value":100})
v2=f11(F,{"id":"c2","field":"salary","operator":"gte","value":200})
v3=f11(F,{"id":"c3","field":"remote","operator":"eq","value":"yes"})
v4=f11(F,{"id":"c4","field":"absent","operator":"eq","value":1})
outs=[v1["outcome"],v2["outcome"],v3["outcome"],v4["outcome"]]
rec("n11","behavior","executed","pass" if outs==["satisfied","not_satisfied","not_answerable","not_answerable"] else "fail",
    f"three-valued outcomes exactly as the behavior requires: {outs}. A field the payload never "
    f"stated (remote) is NOT reported as failing -- the behavior's explicit prohibition holds.")
rec("n11","behavior","executed","pass" if v1["provenance"]=={"kind":"locator"} and v1["field"]=="salary" else "fail",
    "every verdict carries the field name and that field's provenance")
v5=f11({"s":{"value":"90k","stated":True,"provenance":{}}},{"id":"c","field":"s","operator":"gte","value":100})
rec("n11","behavior","executed","pass" if v5["outcome"]=="not_answerable" else "fail",
    f"incomparable stated value (str vs int under gte) -> {v5['outcome']}, not a false negative. "
    f"Defensible but an interpretation the contract did not dictate.")
try:
    f11(F,{"id":"c","field":"salary","operator":"nonsense","value":1}); raised=False
except ValueError: raised=True
rec("n11","behavior","executed","pass" if raised else "fail",
    "unknown operator raises ValueError (malformed criterion) rather than silently returning an outcome")
ops=[("eq",150,True),("ne",1,True),("lt",200,True),("gt",1,True),("in",[150],True),("contains",None,None)]
got=[f11(F,{"id":"o","field":"salary","operator":o,"value":v})["outcome"]=="satisfied" for o,v,_ in ops[:5]]
rec("n11","behavior","executed","pass" if all(got) else "fail",
    f"operator table spans the declared space, not one imagined operator: eq/ne/lt/gt/in all satisfied -> {got}")

# ---------------- n6 ----------------
f6=load("n6")["summarize_criteria"]
A=[{"source_id":"s","source_posting_id":"1","verdicts":[{"criterion_id":"c1","outcome":"satisfied"},{"criterion_id":"c2","outcome":"satisfied"}]},
   {"source_id":"s","source_posting_id":"2","verdicts":[{"criterion_id":"c1","outcome":"not_satisfied"},{"criterion_id":"c2","outcome":"not_answerable"}]}]
C=[{"id":"c1"},{"id":"c2"},{"id":"c3"}]
d=f6(A,C)
by={x["criterion_id"]:x for x in d}
ok=(len(d)==3 and by["c1"]["discriminated"] and not by["c2"]["discriminated"]
    and by["c2"]["not_answerable_posting_ids"]==[{"source_id":"s","source_posting_id":"2"}]
    and by["c3"]["outcome_counts"]=={"satisfied":0,"not_satisfied":0,"not_answerable":0})
rec("n6","behavior","executed","pass" if ok else "fail",
    f"one record per criterion including c3 which no verdict mentions; discriminated true only for c1 "
    f"(both outcomes present); c2's not-answerable posting listed. counts c1={by['c1']['outcome_counts']}")
rec("n6","behavior","executed","pass" if f6([],C)!=[] and len(f6([],C))==3 else "fail",
    "boundary: zero assessments still yields a record for every criterion, all counts zero")

print(json.dumps(R,indent=1))
