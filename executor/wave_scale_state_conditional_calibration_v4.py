"""Deterministic calibration v4 for issue #394.

Iterative development only. No file/network I/O, outcomes, routing, or production authority.
V4 adds a bounded two-axis explicit-ambiguity detector and a year-robust
one-sided INVALID guard while retaining the v3 S/D band and frozen dominance-v1.
"""
from __future__ import annotations
import itertools
import math
import wave_scale_state_conditional_calibration_v1 as v1
import wave_scale_state_conditional_calibration_v2 as v2
import wave_scale_state_conditional_calibration_v3 as v3

YEARS=v1.YEARS
FALSE_INVALID_CAP=0.05
AMBIG_COMPONENT_FALSE_CAP=0.05
DATA_INVALID=v1.DATA_INVALID; SUPPORTED=v1.SUPPORTED; DEVELOPING=v1.DEVELOPING
NOT_DOMINANT=v1.NOT_DOMINANT; AMBIGUOUS=v1.AMBIGUOUS
VALID=v1.VALID; INVALID=v1.INVALID; UNCERTAIN_VALIDITY=v1.UNCERTAIN_VALIDITY
TURNING=v1.TURNING; DEVELOPING_LEG=v1.DEVELOPING_LEG; MORPH_AMBIG=v1.MORPH_AMBIG

STABLE_VALIDITY_DIRECTIONS={
    "close_jump_concentration":"GE",
    "close_range_concentration":"GE",
    "local_jump_isolation_ratio":"GE",
}
AMBIGUITY_AXES=(
    "delta_search_adjusted_bic_vs_one_leg_median",
    "turn_edge_distance_fraction_median",
)

def _finite(x): return v2._finite(x)
def _condition_id(c):
    return f"{c['feature']}:{c['direction']}:{format(c['threshold'],'.17g')}"
def _rule_id(rule):
    if rule["op"]=="NULL": return "NULL"
    return rule["op"]+"|"+"|".join(_condition_id(c) for c in rule["conditions"])
def _cmp(value,direction,threshold):
    x=_finite(value)
    if x is None:return None
    return x>=threshold if direction=="GE" else x<=threshold
def apply_validity_rule(features,rule):
    if rule["op"]=="NULL":return False
    vals=[_cmp(features.get(c["feature"]),c["direction"],c["threshold"]) for c in rule["conditions"]]
    if rule["op"]=="SINGLE":return vals[0]
    if rule["op"]=="OR":
        if True in vals:return True
        return False if all(v is False for v in vals) else None
    raise ValueError("validity rule op")
def _conditions(rows,feature):
    return [{"feature":feature,"direction":STABLE_VALIDITY_DIRECTIONS[feature],"threshold":float(t)}
            for t in v2._midpoints([r.get(feature) for r in rows])]
def _validity_candidates(rows):
    yield {"op":"NULL","conditions":[]}
    tab={f:_conditions(rows,f) for f in sorted(STABLE_VALIDITY_DIRECTIONS)}
    for f in sorted(tab):
        for c in tab[f]:yield {"op":"SINGLE","conditions":[c]}
    for a,b in itertools.combinations(sorted(tab),2):
        for ca in tab[a]:
            for cb in tab[b]:
                yield {"op":"OR","conditions":[ca,cb]}
def fit_validity_guard(records):
    rows=[r["validity"] for r in records]
    invalid=[i for i,r in enumerate(records) if r["reference_state"]==DATA_INVALID]
    non=[i for i,r in enumerate(records) if r["reference_state"]!=DATA_INVALID]
    if not invalid or not non:
        rule={"op":"NULL","conditions":[]}
        return {"fit_status":"INSUFFICIENT_CLASS_SUPPORT","rule":rule,"rule_id":"NULL"}
    years=sorted({r["year"] for r in records})
    best=None
    for rule in _validity_candidates(rows):
        vals=[apply_validity_rule(row,rule) for row in rows]
        per_year={}
        feasible=True
        recalls=[]
        for y in years:
            yi=[i for i,r in enumerate(records) if r["year"]==y and r["reference_state"]==DATA_INVALID]
            yn=[i for i,r in enumerate(records) if r["year"]==y and r["reference_state"]!=DATA_INVALID]
            fp=sum(vals[i] is True for i in yn); fpr=0.0 if not yn else fp/len(yn)
            if yn and fpr>FALSE_INVALID_CAP+1e-15:
                feasible=False;break
            rec=None if not yi else sum(vals[i] is True for i in yi)/len(yi)
            if rec is not None:recalls.append(rec)
            per_year[str(y)]={"invalid_support":len(yi),"noninvalid_support":len(yn),"recall":rec,"false_invalid_rate":fpr}
        if not feasible:continue
        tp=sum(vals[i] is True for i in invalid); fp=sum(vals[i] is True for i in non)
        pooled_rec=tp/len(invalid); pooled_fpr=fp/len(non)
        unknown=sum(v is None for v in vals)/len(vals)
        min_rec=min(recalls) if recalls else 0.0
        key=(-min_rec,-pooled_rec,pooled_fpr,unknown,len(rule["conditions"]),_rule_id(rule))
        metrics={"positive_support":len(invalid),"negative_support":len(non),"true_positive":tp,"false_positive":fp,
                 "recall":pooled_rec,"false_positive_rate":pooled_fpr,"unknown_rate":unknown,
                 "min_training_year_recall":min_rec,"per_year":per_year}
        item=(key,rule,metrics)
        if best is None or key<best[0]:best=item
    if best is None:raise RuntimeError("NULL validity rule must be feasible")
    return {"fit_status":"FITTED","rule":best[1],"rule_id":_rule_id(best[1]),"metrics":best[2],
            "semantics":"YEAR_ROBUST_ONE_SIDED_INVALID_GUARD"}
def predict_validity(record,fit):
    v=apply_validity_rule(record["validity"],fit["rule"])
    if v is True:return INVALID
    if v is False:return VALID
    return UNCERTAIN_VALIDITY

def _interval_id(axis,lo,hi):
    return f"{axis}|LO>{format(lo,'.17g')}|HI<={format(hi,'.17g')}"
def _interval_fire(features,fit):
    if fit.get("rule") is None:return False
    x=_finite(features.get(fit["rule"]["axis"]))
    if x is None:return False
    return fit["rule"]["lo"] < x <= fit["rule"]["hi"]
def fit_ambiguity_interval(records,axis):
    train=[r for r in records if r["reference_state"] in {SUPPORTED,DEVELOPING,AMBIGUOUS}]
    amb=[r for r in train if r["reference_state"]==AMBIGUOUS]
    non=[r for r in train if r["reference_state"] in {SUPPORTED,DEVELOPING}]
    if not amb or not non:
        return {"fit_status":"INSUFFICIENT_CLASS_SUPPORT","rule":None,"rule_id":"NONE",
                "metrics":{"ambiguous_support":len(amb),"nonambiguous_support":len(non)}}
    points=v2._boundary_points([r["morphology"].get(axis) for r in train])
    best=None
    for i,lo in enumerate(points):
        for hi in points[i:]:
            if hi<lo:continue
            def fire(r):
                x=_finite(r["morphology"].get(axis))
                return x is not None and lo < x <= hi
            tp=sum(fire(r) for r in amb); fp=sum(fire(r) for r in non)
            rec=tp/len(amb); fpr=fp/len(non)
            if fpr>AMBIG_COMPONENT_FALSE_CAP+1e-15:continue
            rid=_interval_id(axis,float(lo),float(hi))
            key=(-rec,fp,rid)
            metrics={"ambiguous_support":len(amb),"nonambiguous_support":len(non),
                     "true_ambiguous":tp,"false_ambiguous":fp,"ambiguous_recall":rec,
                     "false_ambiguous_rate":fpr}
            item=(key,{"axis":axis,"lo":float(lo),"hi":float(hi)},rid,metrics)
            if best is None or key<best[0]:best=item
    if best is None:
        return {"fit_status":"NO_FEASIBLE_INTERVAL","rule":None,"rule_id":"NONE",
                "metrics":{"ambiguous_support":len(amb),"nonambiguous_support":len(non)}}
    return {"fit_status":"FITTED","rule":best[1],"rule_id":best[2],"metrics":best[3]}
def fit_explicit_ambiguity(records):
    fits={axis:fit_ambiguity_interval(records,axis) for axis in AMBIGUITY_AXES}
    return {"fits":fits,"component_false_cap":AMBIG_COMPONENT_FALSE_CAP,
            "semantics":"OR_OF_TWO_INDEPENDENT_CAPPED_INTERVALS"}
def predict_explicit_ambiguity(record,fit):
    return any(_interval_fire(record["morphology"],f) for f in fit["fits"].values())

def fit_morphology_band(records): return v3.fit_morphology_band(records)
def predict_morphology(record,fit): return v3.predict_morphology(record,fit)
def _validate_records(records): return v2._validate_records(records)
def _dominance_training(records,validity_predictions,morphology_predictions,branch):
    return v2._dominance_training(records,validity_predictions,morphology_predictions,branch)

def fit_loyo_development(records):
    _validate_records(records)
    ordered=sorted(records,key=lambda r:(r["year"],r["panel_id"]))
    predictions=[];fold_models=[]
    for held in YEARS:
        train=[r for r in ordered if r["year"]!=held];test=[r for r in ordered if r["year"]==held]
        vf=fit_validity_guard(train);af=fit_explicit_ambiguity(train);mf=fit_morphology_band(train)
        tval=[predict_validity(r,vf) for r in train]
        tamb=[predict_explicit_ambiguity(r,af) for r in train]
        tmorph_component=[predict_morphology(r,mf) for r in train]
        tmorph=[MORPH_AMBIG if v!=VALID or a else m for v,a,m in zip(tval,tamb,tmorph_component)]
        dom={}
        for branch in (TURNING,DEVELOPING_LEG):
            branch_train=_dominance_training(train,tval,tmorph,branch)
            dom[branch]=v1.fit_dominance_rule(branch_train,branch)
        fold_models.append({"held_year":held,"train_years":[y for y in YEARS if y!=held],
                            "train_support":len(train),"test_support":len(test),
                            "validity":{"invalid":vf},"explicit_ambiguity":af,
                            "morphology":mf,"dominance":dom})
        for r in test:
            val=predict_validity(r,vf); explicit=predict_explicit_ambiguity(r,af); mc=predict_morphology(r,mf)
            if val==INVALID: final,reason=DATA_INVALID,"VALIDITY_REJECT"
            elif val==UNCERTAIN_VALIDITY: final,reason=AMBIGUOUS,"VALIDITY_UNCERTAIN"
            elif explicit: final,reason=AMBIGUOUS,"EXPLICIT_AMBIGUITY_DETECTOR"
            else:
                morph=mc
                final,reason=v2._final(r,val,morph,dom)
            predictions.append({"panel_id":r["panel_id"],"year":held,"reference_state":r["reference_state"],
                                "validity_prediction":val,"explicit_ambiguity_prediction":explicit,
                                "morphology_component_prediction":mc,
                                "operational_morphology":MORPH_AMBIG if val!=VALID or explicit else mc,
                                "final_state":final,"final_reason":reason})
    if len(predictions)!=len(records) or len({p["panel_id"] for p in predictions})!=len(records):
        raise RuntimeError("OOF prediction cardinality")
    return {"schema_id":"csi1000.scale_state_conditional_loyo@4.0",
            "population_role":"ITERATIVE_DEVELOPMENT_EVIDENCE_NOT_FRESH_OOS",
            "years":list(YEARS),"predictions":predictions,"fold_models":fold_models,
            "dominance_family":"V1_FROZEN_CONTROL_UNCHANGED",
            "full_192_fit_performed":False,"production_authority":False}
