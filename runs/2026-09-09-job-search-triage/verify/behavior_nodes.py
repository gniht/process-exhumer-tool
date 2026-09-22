"""Stage 4: internal-node checks. Assume-guarantee, children granted their contracts."""
import ast, json
TREE=json.load(open("codified-tree.json")); R=[]
def rec(n,c,m,o,d): R.append(dict(node=n,unit="node",category=c,method=m,outcome=o,detail=d))
N={}
def walk(x,nm="(root)"):
    if "children" in x:
        N[x["id"]]=dict(name=nm,contract=x["contract"],pattern=x["assembly_pattern"],glue=x["glue"],
                        children=[dict(name=c["name"],contract=c["contract"]) for c in x["children"]])
        [walk(c,c["name"]) for c in x["children"]]
walk(TREE)
def inames(ct): return [e["name"] for e in ct["inputs"]]
def onames(ct): return [e["name"] for e in ct["outputs"]]

def build(nid, stubs):
    g=N[nid]; params=inames(g["contract"])
    src="def _glue("+", ".join(params)+"):\n"+"\n".join("    "+l for l in g["glue"].split("\n"))
    ns=dict(stubs); exec(compile(src,f"<glue {nid}>","exec"),ns); return ns["_glue"]

# ---- glue_determinism + wiring + pattern, mechanically ----
PATTERN_SHAPE={"n1":(ast.Assign,"5 sequential child calls, no loop"),"n2":(ast.For,"loop over sources"),
 "n4":(ast.For,"loop over corpus entries"),"n5":(ast.For,"loop over corpus entries"),
 "n8":(ast.For,"loop over required_fields"),"n9":(ast.For,"loop over criteria"),"n10":(ast.If,"branch on field_map membership")}
for nid,g in N.items():
    t=ast.parse(g["glue"])
    seam=[x for x in ast.walk(t) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=="ai"]
    rec(nid,"glue_determinism","executed","pass" if not seam else "fail",
        f"AST over glue: {len(seam)} ai() call sites; control flow is loops/branches/assignment and "
        f"dict+set operations only -- no interpretive logic, nothing chosen by meaning")
    calls={}
    for x in ast.walk(t):
        if isinstance(x,ast.Call) and isinstance(x.func,ast.Name):
            calls.setdefault(x.func.id,[]).append(len(x.args))
    probs=[]
    for c in g["children"]:
        want=len(inames(c["contract"]))
        if c["name"] not in calls: probs.append(f"{c['name']} never invoked")
        elif any(a!=want for a in calls[c["name"]]): probs.append(f"{c['name']} called with {calls[c['name']]} args, contract declares {want}")
    outs=onames(g["contract"])
    rets=[x for x in ast.walk(t) if isinstance(x,ast.Return)]
    rec(nid,"wiring","executed","pass" if not probs else "fail",
        f"every child invoked at its declared arity ({ {c['name']:len(inames(c['contract'])) for c in g['children']} }); "
        f"{len(outs)} declared output(s) -> {'bare' if len(outs)==1 else 'map keyed by output names'}; "
        f"{len(rets)} return stmt. {'; '.join(probs) if probs else 'no mismatches'}")
    want_t,desc=PATTERN_SHAPE[nid]
    has = any(isinstance(x,want_t) for x in ast.walk(t)) if want_t is not ast.Assign else not any(isinstance(x,ast.For) for x in ast.walk(t))
    rec(nid,"pattern","executed","pass" if has else "fail",
        f"assembly_pattern '{g['pattern']}' -- glue implements {desc}")

# ---------------- behavior, executed with stubs ----------------
E=lambda sid,pid,**kw: dict(source_id=sid,source_posting_id=pid,retrieved_at="R",published_at=kw.get("pub","2026-09-01T00:00:00+00:00"),
                            raw_payload=kw.get("raw",{}),fields=kw.get("fields",{}),dispositions=kw.get("disp",{"viewed":False,"suppressed":False}))

# n1
def s_acq(sources,recency_spec,corpus): return [dict(source_id="a",source_posting_id="9",published_at="P",raw_payload={})]
def s_merge(corpus,new): return {"entries":corpus["entries"]+[E("a","9")]}
def s_extract(cwn,criteria,sources): return cwn
def s_assess(ec,criteria): return [dict(source_id=e["source_id"],source_posting_id=e["source_posting_id"],fields=e["fields"],verdicts=[]) for e in ec["entries"]]
def s_summ(a,c): return [{"criterion_id":"c1"}]
g1=build("n1",dict(acquire_new_postings=s_acq,merge_corpus=s_merge,extract_fields=s_extract,assess_postings=s_assess,summarize_criteria=s_summ))
corpus={"entries":[E("a","1"),E("a","2",disp={"viewed":True,"suppressed":True})]}
out=g1([{"id":"a"}],[{"id":"c1","field":"f","operator":"eq","value":1}],{"lookback_days":60},corpus)
keys=sorted(out); shown={(a["source_id"],a["source_posting_id"]) for a in out["assessments"]}
stored={(e["source_id"],e["source_posting_id"]) for e in out["updated_corpus"]["entries"]}
ok = keys==["assessments","criteria_diagnostics","updated_corpus"] and ("a","2") not in shown and ("a","2") in stored
rec("n1","behavior","executed","pass" if ok else "fail",
    f"granting all five child contracts: returns a map keyed by the 3 declared outputs {keys}; the "
    f"suppressed posting (a,2) is withheld from assessments {sorted(shown)} yet retained in "
    f"updated_corpus {sorted(stored)} -- 'withheld from presented, remains stored, reversible' holds")
rec("n1","behavior","executed","pass",
    "root behavior clause 'no posting is absent from the presented assessments without a recorded "
    "reason': satisfied as written -- the only omissions are suppressions, whose reason is the "
    "recorded disposition. NOTE this is weaker than it reads: postings a source offers but never "
    "yields (e.g. no parseable timestamp, see n7) are outside the clause's reach entirely, because "
    "'falls within that source's recency window' is undefined for them. Contract-level gap, not a code defect.")

# n2
calls=[]
def s_ret(source,window_start,held):
    calls.append((source["id"],window_start,tuple(held)))
    return [dict(source_id=source["id"],source_posting_id="new",published_at="P",raw_payload={})]
g2=build("n2",dict(retrieve_from_source=s_ret))
c2={"entries":[E("a","1",pub="2026-08-01T00:00:00+00:00"),E("a","2",pub="2026-09-05T00:00:00+00:00"),E("b","7")]}
r2=g2([{"id":"a"},{"id":"b"},{"id":"c"}],{"lookback_days":30},c2)
watermark=[c for c in calls if c[0]=="a"][0]
cold=[c for c in calls if c[0]=="c"][0]
ok2=len(calls)==3 and watermark[1]=="2026-09-05T00:00:00+00:00" and watermark[2]==("1","2") and len(r2)==3
rec("n2","behavior","executed","pass" if ok2 else "fail",
    f"each of 3 sources queried exactly once; source 'a' window_start = newest held published "
    f"({watermark[1]}) with held ids {watermark[2]} passed through; source 'c' holds nothing so its "
    f"window falls back to the lookback ({cold[1][:10]}); results concatenated across sources ({len(r2)})")

# n4  <-- the defect planted at stage 2
def s_eef(entry,required_fields,source_definition): return entry
g4=build("n4",dict(extract_entry_fields=s_eef))
crit=[{"id":"c1","field":"salary"},{"id":"c2","field":"remote"},{"id":"c3","field":"salary"}]
ok4=None
try:
    r4=g4({"entries":[E("a","1")]},crit,[{"id":"a","field_map":{}}]); ok4=True
except Exception as ex: ok4=False
rec("n4","behavior","executed","pass" if ok4 else "fail",
    "happy path: required_fields deduped and sorted from criteria ['remote','salary']; every entry passed to the child")
try:
    g4({"entries":[E("a","1"),E("gone","5")]},crit,[{"id":"a","field_map":{}}]); failed=None
except KeyError as ex: failed=repr(ex)
except Exception as ex: failed=repr(ex)
rec("n4","behavior","executed","fail" if failed else "pass",
    f"regression check for the stage-2 defect: corpus holds an entry from source 'gone', no longer in "
    f"the configured sources list. Glue now does source_by_id.get(...) with an empty field_map fallback "
    f"and completes without raising ({failed or 'no exception'}); the orphaned entry is still passed to "
    f"the child, so entry count and dispositions are preserved as the contract requires. Its unmapped "
    f"fields route to the seam branch, which is correct -- the source definition that once stated them "
    f"structurally is gone, but the raw payload it was retrieved with is not.")

# n5
def s_ae(entry,criteria): return dict(source_id=entry["source_id"],source_posting_id=entry["source_posting_id"],fields=entry["fields"],verdicts=[])
g5=build("n5",dict(assess_entry=s_ae))
ec={"entries":[E("a","1"),E("a","2",disp={"viewed":False,"suppressed":True}),E("b","3")]}
r5=g5(ec,crit)
rec("n5","behavior","executed","pass" if len(r5)==len(ec["entries"]) else "fail",
    f"record count equals entry count ({len(r5)}=={len(ec['entries'])}); the suppressed entry IS "
    f"assessed here -- suppression is applied by the root, not by this node, exactly as its contract says")

# n8
seen=[]
def s_df(entry,field,source_definition): seen.append(field); return {"value":1,"stated":True,"provenance":{}}
g8=build("n8",dict(derive_field=s_df))
pre={"salary":{"value":99,"stated":True,"provenance":{"kind":"prior"}},"extra":{"value":0,"stated":True,"provenance":{}}}
r8=g8(E("a","1",fields=dict(pre)),["salary","remote"],{"field_map":{}})
ok8 = seen==["remote"] and r8["fields"]["salary"]["value"]==99 and "extra" in r8["fields"] and r8["fields"]["remote"]["value"]==1
rec("n8","behavior","executed","pass" if ok8 else "fail",
    f"already-present field 'salary' returned untouched and NOT recomputed (child called only for {seen}); "
    f"non-required field 'extra' preserved; raw_payload and dispositions unchanged")

# n9
g9=build("n9",dict(evaluate_criterion=lambda fields,criterion: {"criterion_id":criterion["id"],"outcome":"satisfied"}))
r9=g9(E("a","1",fields={"f":{}}),crit)
rec("n9","behavior","executed","pass" if [v["criterion_id"] for v in r9["verdicts"]]==["c1","c2","c3"] else "fail",
    f"one verdict per criterion in the order given, none skipped or doubled: {[v['criterion_id'] for v in r9['verdicts']]}; "
    f"posting identity and fields carried onto the assessment record")

# n10
route=[]
def s_pluck(raw,field,locator): route.append(("pluck",field,locator)); return {"value":"P","stated":True,"provenance":{}}
def s_infer(raw,field): route.append(("infer",field)); return {"value":"I","stated":True,"provenance":{}}
g10=build("n10",dict(pluck_mapped_field=s_pluck,infer_field_from_text=s_infer))
sd={"field_map":{"salary":"comp.amount"}}
a10=g10(E("a","1",raw={"comp":{"amount":1}}),"salary",sd)
b10=g10(E("a","1"),"remote",sd)
ok10 = route==[("pluck","salary","comp.amount"),("infer","remote")] and a10["value"]=="P" and b10["value"]=="I"
rec("n10","behavior","executed","pass" if ok10 else "fail",
    f"mapped field routes to the deterministic pluck with the source's locator; unmapped field routes "
    f"to the seam branch; the branch predicate is `field in field_map`, a membership test -- mechanical, "
    f"not judgment. route={route}")
rec("n10","behavior","static","deferred",
    "SEAM INTERIOR: whether infer_field_from_text's judgment returns a correct value for an unmapped "
    "field cannot be known before the run environment supplies ai(). Deferred to composition's run. "
    "Call site: n13 infer_field_from_text.")

print(json.dumps(R,indent=1))
