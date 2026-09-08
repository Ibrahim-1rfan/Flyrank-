"""Review demonstration for the method preferred before the June test."""
import numpy as np
import pandas as pd
from warehouse_capstone import Warehouse,eligible_features,attach_labels,evaluate,dump

def build_policy_review(root,receipt):
    method=receipt['validation_preferred_method']
    assert method in ['momentum_rule','volume_rule'],'This review builder covers the two transparent rules.'
    w=Warehouse(root);clients,content=w.dimensions()
    march,_=eligible_features(w.month('2026-03'),'2026-03',clients,content)
    groups=np.random.default_rng(42).permutation(np.sort(march.client_hash_id.unique()))
    test_groups=set(groups[:receipt['partition_clients']['test']])
    may,_=eligible_features(w.month('2026-05'),'2026-05',clients,content)
    may=may[may.client_hash_id.isin(test_groups)]
    test,coverage=attach_labels(may,w.month('2026-06'),'2026-06')
    column='momentum_score' if method=='momentum_rule' else 'volume_score'
    measured=evaluate(test,test[column].to_numpy())
    assert measured==receipt['test_metrics'][method]
    rows=[]
    for rank,(_,row) in enumerate(test.sort_values(column,ascending=False,kind='stable').head(20).iterrows(),1):
        volume='500-999' if row.impressions<1000 else '1,000-9,999' if row.impressions<10000 else '10,000+'
        if pd.notna(row.weighted_position) and row.weighted_position<=20 and row.ctr_pct<.5:
            action='Review recent loss, snippet, and intent'
            reason='past_decline_and_low_ctr'
        else:
            action='Check why recent visibility fell'
            reason='past_decline_with_demand'
        rows.append({'rank':rank,'rule_score':round(float(row[column]),3),'volume_band':volume,
                     'action':action,'reason':reason,'evidence':'Review required; score is not a probability',
                     'what_could_be_wrong':'Seasonality, tracking changes, or related-page gains'})
    result={'method':method,'selected_from':'April-to-May validation, before June evaluation',
            'scope':'20 evaluable held-out May pages, using feature-only rule scores',
            'test_metrics':measured,'rows':rows,'checks':{'matches_recorded_final_rule_metrics':True,'matches_validation_preferred_method':True}}
    dump(w.out/'warehouse_policy_review.json',result)
    w.con.close()
    return result
