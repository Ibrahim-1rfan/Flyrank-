"""Warehouse experiment: previous-month features, next-month decline, held-out clients.
Private page-level caches stay in ignored Parquet files. Public receipts are aggregates.
"""
from pathlib import Path
import calendar
import hashlib
import json
from datetime import datetime, timezone
import duckdb
import numpy as np
import pandas as pd
from huggingface_hub import get_token
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, confusion_matrix

REVISION='50cbf7c3909d07be4d1b5906b4d09e882e5acbf2'
BASE=f'hf://datasets/FlyRank/internship-warehouse@{REVISION}'
KEYS=['client_hash_id','content_hash_id']
FEATURES=['log_impressions','log_clicks','ctr_pct','weighted_position','active_day_share',
          'click_day_share','daily_impression_cv','half_month_change','gsc_coverage','content_age_days']
CONFIG={'version':2,'grain_policy':'exclude any page-month with duplicate daily records before features or labels','seed':42,'revision':REVISION,'min_feature_impressions':500,
        'min_tracking_coverage':0.9,'min_content_age_days':90,'decline_ratio':0.8,
        'training_pair':['2026-03','2026-04'],'validation_pair':['2026-04','2026-05'],
        'test_pair':['2026-05','2026-06'],'client_partitions':'60/20/20 from March-eligible clients',
        'primary_metric':'precision_at_50_expected_ties','features':FEATURES,
        'baseline':'max(0,-half_month_change) * log1p(feature_month_impressions)',
        'secondary_baseline':'feature_month_impressions',
        'final_refit':'March-April and April-May from training and validation clients only'}

def dump(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def month_days(month):
    year,number=map(int,month.split('-'))
    return calendar.monthrange(year,number)[1]

class Warehouse:
    def __init__(self,root):
        self.root=Path(root)
        self.out=self.root/'work/outputs'
        self.cache=self.out/'warehouse_cache'
        self.cache.mkdir(parents=True,exist_ok=True)
        self.con=duckdb.connect()
        self.con.execute("SET threads=2")
        self.con.execute("SET memory_limit='2GB'")
        self.con.execute("SET temp_directory='"+(self.cache/'duckdb_tmp').as_posix()+"'")
        self.con.execute('LOAD httpfs')
        self._authenticated=False
        self.quality={}
        self.manifest_path=self.out/'warehouse_cache_manifest.json'
        self.manifest=json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {'revision':REVISION,'files':{}}
        assert self.manifest['revision']==REVISION
    def authenticate(self):
        if self._authenticated:return
        token=get_token()
        if not token:raise RuntimeError('Sign in locally with hf auth login before the first warehouse run.')
        try:self.con.execute("CREATE SECRET capstone_hf (TYPE huggingface, TOKEN '"+token.replace("'","''")+"')")
        except Exception:raise RuntimeError('Could not register the saved Hugging Face login.') from None
        self._authenticated=True
    def cache_query(self,name,query):
        path=self.cache/(name+'.parquet')
        query_hash=hashlib.sha256(query.encode()).hexdigest()
        entry=self.manifest['files'].get(name)
        if path.exists() and entry:
            assert entry['query_sha256']==query_hash,'Query changed: use a new cache version.'
            assert entry['sha256']==fingerprint(path),'Cached data changed unexpectedly.'
            return self.con.sql("SELECT * FROM read_parquet('"+path.as_posix()+"')").df()
        self.authenticate()
        print('Aggregating '+name+' from the pinned warehouse release...',flush=True)
        try:
            result=self.con.sql(query).df()
        except Exception as error:
            raise RuntimeError('Warehouse read failed ('+type(error).__name__+'). Check access/network; no data or credentials printed.') from None
        self.con.register('capstone_cache_result',result)
        self.con.execute("COPY capstone_cache_result TO '"+path.as_posix()+"' (FORMAT PARQUET, COMPRESSION ZSTD)")
        self.con.unregister('capstone_cache_result')
        self.manifest['files'][name]={'rows':len(result),'query_sha256':query_hash,'sha256':fingerprint(path)}
        dump(self.manifest_path,self.manifest)
        print('Cached '+name+': '+format(len(result),',')+' aggregate rows.',flush=True)
        return result
    def inventory(self):
        target=self.out/'warehouse_inventory.json'
        if target.exists():
            result=json.loads(target.read_text());assert result['revision']==REVISION
            return result
        self.authenticate()
        print('Checking warehouse row count and date range from Parquet metadata...',flush=True)
        row=self.con.sql(f"SELECT count(*),min(report_date),max(report_date) FROM read_parquet('{BASE}/fact_content_daily_performance/**/*.parquet')").fetchone()
        assert row[0]==78835655 and str(row[1])=='2025-01-27' and str(row[2])=='2026-06-30'
        result={'revision':REVISION,'daily_rows':row[0],'start':str(row[1]),'end':str(row[2])}
        dump(target,result)
        return result
    def dimensions(self):
        clients=self.cache_query('clients_v1',f"SELECT client_hash_id,gsc_data_start FROM read_parquet('{BASE}/dim_clients.parquet')")
        content=self.cache_query('content_v1',f"SELECT client_hash_id,content_hash_id,content_created_date FROM read_parquet('{BASE}/dim_content.parquet')")
        assert len(clients)==104 and clients['client_hash_id'].is_unique
        assert len(content)==519606 and not content.duplicated(KEYS).any()
        return clients,content
    def month(self,month):
        # Scan every daily row once for this partition; bring only page-month aggregates into Python.
        query=f"""
        SELECT client_hash_id, content_hash_id,
               count(*) AS raw_rows, count(DISTINCT report_date) AS distinct_dates,
               min(report_date) AS first_date,max(report_date) AS last_date,
               count(*) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL) AS observed_days,
               count(*) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL AND day(report_date)<=15) AS h1_days,
               count(*) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL AND day(report_date)>15) AS h2_days,
               sum(gsc_impressions) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL) AS impressions,
               sum(gsc_clicks) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL) AS clicks,
               sum(gsc_sum_position) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL) AS sum_position,
               sum(gsc_impressions) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL AND gsc_sum_position IS NOT NULL) AS position_impressions,
               sum(gsc_impressions) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL AND day(report_date)<=15) AS h1_impressions,
               sum(gsc_impressions) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL AND day(report_date)>15) AS h2_impressions,
               stddev_pop(gsc_impressions) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks IS NOT NULL) AS daily_std,
               count(*) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions>0 AND gsc_clicks IS NOT NULL) AS active_days,
               count(*) FILTER (WHERE gsc_data_available IS TRUE AND gsc_impressions IS NOT NULL AND gsc_clicks>0) AS click_days,
               count(*) FILTER (WHERE gsc_data_available IS TRUE AND (gsc_impressions<0 OR gsc_clicks<0 OR gsc_sum_position<0)) AS invalid_rows
        FROM read_parquet('{BASE}/fact_content_daily_performance/month={month}/data_0.parquet')
        GROUP BY client_hash_id,content_hash_id
        """
        frame=self.cache_query('month_'+month.replace('-','_')+'_v1',query)
        duplicate=frame['raw_rows'].ne(frame['distinct_dates'])
        self.quality[month]={'daily_rows':int(frame.raw_rows.sum()),'page_months':len(frame),
            'start':str(frame.first_date.min().date()),'end':str(frame.last_date.max().date()),
            'duplicate_daily_rows':int((frame.raw_rows-frame.distinct_dates).sum()),
            'excluded_duplicate_page_months':int(duplicate.sum()),
            'excluded_raw_rows_in_duplicate_groups':int(frame.loc[duplicate,'raw_rows'].sum()),
            'negative_measurement_rows':int(frame.invalid_rows.sum())}
        if duplicate.any():
            print(f'Quality exclusion in {month}: {int(duplicate.sum()):,} page-months with duplicate daily records.',flush=True)
        frame=frame.loc[~duplicate].copy()
        assert (frame['raw_rows']==frame['distinct_dates']).all()
        assert frame['invalid_rows'].sum()==0,'Negative search measurements'
        assert str(frame['first_date'].min().date())==month+'-01'
        assert str(frame['last_date'].max().date())==month+'-'+str(month_days(month))
        assert not frame.duplicated(KEYS).any()
        return frame

def eligible_features(monthly,month,clients,content):
    end=pd.Timestamp(month+'-'+str(month_days(month)))
    start=pd.Timestamp(month+'-01')
    frame=monthly.merge(content,on=KEYS,how='left',validate='one_to_one').merge(clients,on='client_hash_id',how='left',validate='many_to_one')
    frame['content_age_days']=(end-pd.to_datetime(frame['content_created_date'])).dt.days
    coverage=frame['observed_days']/month_days(month)
    masks=[frame['gsc_data_start'].notna() & (pd.to_datetime(frame['gsc_data_start'])<=start),
           coverage>=CONFIG['min_tracking_coverage'],
           frame['content_age_days']>=CONFIG['min_content_age_days'],
           frame['impressions']>=CONFIG['min_feature_impressions']]
    remaining=np.ones(len(frame),dtype=bool);flow={'page_month_rows':len(frame)}
    for name,mask in zip(['history_started','feature_tracking_90pct','age_90_days','impressions_500'],masks):
        remaining &= mask.fillna(False).to_numpy();flow[name]=int(remaining.sum())
    frame=frame.loc[remaining].copy()
    frame['feature_month']=month
    frame['feature_daily_rate']=frame['impressions']/frame['observed_days']
    frame['log_impressions']=np.log1p(frame['impressions'])
    frame['log_clicks']=np.log1p(frame['clicks'])
    frame['ctr_pct']=100*frame['clicks']/frame['impressions']
    frame['weighted_position']=frame['sum_position']/frame['position_impressions'].replace(0,np.nan)
    frame['active_day_share']=frame['active_days']/frame['observed_days']
    frame['click_day_share']=frame['click_days']/frame['observed_days']
    frame['daily_impression_cv']=frame['daily_std']/frame['feature_daily_rate']
    h1=frame['h1_impressions']/frame['h1_days'].replace(0,np.nan)
    h2=frame['h2_impressions']/frame['h2_days'].replace(0,np.nan)
    frame['half_month_change']=((h2-h1)/h1.replace(0,np.nan)).clip(-1,10)
    frame['gsc_coverage']=frame['observed_days']/month_days(month)
    frame['momentum_score']=(-frame['half_month_change'].fillna(0)).clip(lower=0)*frame['log_impressions']
    frame['volume_score']=frame['impressions']
    frame[FEATURES]=frame[FEATURES].replace([np.inf,-np.inf],np.nan)
    return frame.sort_values(KEYS).reset_index(drop=True),flow

def attach_labels(features,outcomes,outcome_month):
    later=outcomes[KEYS+['observed_days','impressions']].rename(columns={'observed_days':'outcome_days','impressions':'outcome_impressions'})
    joined=features.merge(later,on=KEYS,how='left',validate='one_to_one')
    valid=joined['outcome_days']/month_days(outcome_month)>=CONFIG['min_tracking_coverage']
    summary={'eligible_feature_pages':len(joined),'evaluable_pages':int(valid.sum()),'unobserved_outcomes':int((~valid).sum())}
    frame=joined.loc[valid].copy()
    frame['outcome_daily_rate']=frame['outcome_impressions']/frame['outcome_days']
    frame['label']=(frame['outcome_daily_rate']<CONFIG['decline_ratio']*frame['feature_daily_rate']).astype(int)
    frame['outcome_month']=outcome_month
    assert (pd.to_datetime(frame['feature_month'])<pd.Timestamp(outcome_month+'-01')).all()
    return frame.reset_index(drop=True),summary

def ranked_precision(y,scores,k):
    y=np.asarray(y);scores=np.asarray(scores);k=min(k,len(y))
    cutoff=np.sort(scores)[-k];above=scores>cutoff;tied=scores==cutoff
    slots=k-int(above.sum());fixed=int(y[above].sum());positives=int(y[tied].sum());negatives=int(tied.sum())-positives
    return {'expected':float((fixed+slots*y[tied].mean())/k),
            'minimum':float((fixed+max(0,slots-negatives))/k),
            'maximum':float((fixed+min(slots,positives))/k),'boundary_ties':int(tied.sum())}

def evaluate(frame,scores):
    y=frame['label'].to_numpy();values=np.asarray(scores)
    assert len(y)==len(values) and np.isfinite(values).all() and len(np.unique(y))==2
    result={'rows':len(y),'positives':int(y.sum()),'positive_rate':float(y.mean()),
            'roc_auc':float(roc_auc_score(y,values)),'average_precision':float(average_precision_score(y,values))}
    for k in [20,50,100]:
        ties=ranked_precision(y,values,k)
        result[f'precision_at_{k}']=ties['expected'];result[f'ties_at_{k}']=ties
    return result

def candidates():
    return {'logistic_regression':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),StandardScaler(),LogisticRegression(class_weight='balanced',max_iter=1500,random_state=42)),
            'decision_tree':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),DecisionTreeClassifier(max_depth=5,min_samples_leaf=50,class_weight='balanced',random_state=42)),
            'random_forest':make_pipeline(SimpleImputer(strategy='median',add_indicator=True),RandomForestClassifier(n_estimators=200,max_depth=8,min_samples_leaf=50,class_weight='balanced_subsample',n_jobs=2,random_state=42))}


def run_warehouse(root):
    root=Path(root);w=Warehouse(root)
    inventory=w.inventory()
    clients,content=w.dimensions()
    months={m:w.month(m) for m in ['2026-03','2026-04','2026-05']}
    feature_frames={};feature_flows={}
    for month,frame in months.items():
        feature_frames[month],feature_flows[month]=eligible_features(frame,month,clients,content)
    # Define all client partitions from March feature eligibility, before looking at any labels.
    cohort_clients=np.sort(feature_frames['2026-03']['client_hash_id'].unique())
    assert len(cohort_clients)>=10,'Insufficient March clients for three separate groups.'
    shuffled=np.random.default_rng(42).permutation(cohort_clients)
    n_hold=max(2,round(.2*len(shuffled)))
    test_clients=set(shuffled[:n_hold]);validation_clients=set(shuffled[n_hold:2*n_hold]);train_clients=set(shuffled[2*n_hold:])
    assert not train_clients.intersection(validation_clients|test_clients)
    assert not validation_clients.intersection(test_clients)
    march_april,flow_train=attach_labels(feature_frames['2026-03'],months['2026-04'],'2026-04')
    april_may,flow_validation=attach_labels(feature_frames['2026-04'],months['2026-05'],'2026-05')
    train=march_april[march_april['client_hash_id'].isin(train_clients)].copy()
    validation=april_may[april_may['client_hash_id'].isin(validation_clients)].copy()
    assert len(train)>=500 and len(validation)>=100 and train.label.nunique()==2 and validation.label.nunique()==2
    assert set(FEATURES).isdisjoint({'label','outcome_days','outcome_impressions','outcome_daily_rate',*KEYS})
    print(f'Training on {len(train):,} page-periods; comparing on {len(validation):,} later pages from separate clients.',flush=True)
    val_scores={'momentum_rule':validation['momentum_score'].to_numpy(),'volume_rule':validation['volume_score'].to_numpy()}
    model_candidates=candidates()
    for name,model in model_candidates.items():
        print('Fitting '+name+'...',flush=True)
        model.fit(train[FEATURES],train['label'])
        val_scores[name]=model.predict_proba(validation[FEATURES])[:,1]
    val_metrics={name:evaluate(validation,values) for name,values in val_scores.items()}
    def order(name):
        r=val_metrics[name]
        return r['precision_at_50'],r['average_precision'],r['roc_auc']
    selected=max(model_candidates,key=order)
    recommended=max(val_scores,key=order)
    # Freeze choices and the exact source before opening June outcomes.
    signature=hashlib.sha256(json.dumps(CONFIG,sort_keys=True).encode()).hexdigest()
    source_hash=fingerprint(Path(__file__))
    selection_path=w.out/'warehouse_selection_v2.json'
    selection={'config':CONFIG,'config_sha256':signature,'source_sha256':source_hash,
               'selected_model':selected,'validation_preferred_method':recommended,
               'validation_metrics':val_metrics,'train_rows':len(train),'validation_rows':len(validation),
               'client_partition_counts':{'training':len(train_clients),'validation':len(validation_clients),'test':len(test_clients)},
               'partition_hash':hashlib.sha256('|'.join(map(str,shuffled)).encode()).hexdigest(),
               'selected_before_june_read':True}
    if selection_path.exists():
        previous=json.loads(selection_path.read_text())
        for key in ['config_sha256','source_sha256','selected_model','validation_preferred_method','partition_hash']:
            assert previous[key]==selection[key],f'Frozen selection changed: {key}. Start a separately named experiment instead.'
        selection['first_selection_utc']=previous['first_selection_utc']
    else:
        earlier_path=w.out/'warehouse_selection_before_grain_fix.json'
        if earlier_path.exists():
            earlier=json.loads(earlier_path.read_text())
            for key in ['selected_model','validation_preferred_method','partition_hash','validation_metrics','train_rows','validation_rows']:
                assert earlier[key]==selection[key],f'Pre-June model choice changed: {key}'
            selection['first_selection_utc']=earlier['first_selection_utc']
        else:
            selection['first_selection_utc']=datetime.now(timezone.utc).isoformat()
    earlier_path=w.out/'warehouse_selection_before_grain_fix.json'
    if earlier_path.exists():
        selection['quality_revision']={'reason':'First June evaluation stopped at duplicate-grain guard before labels or metrics were evaluated. Exclude affected page-months under one policy for all months; no model reselection.',
            'original_selection_sha256':fingerprint(earlier_path),'original_source_sha256':json.loads(earlier_path.read_text())['source_sha256'],
            'original_source_file':'work/scripts/archive/warehouse_capstone_before_grain_fix.py',
            'model_choice_and_validation_results_unchanged':True}
    dump(selection_path,selection)
    print('Model choice frozen: '+selected+'. Now preparing May-to-June final evaluation.',flush=True)
    # Final fit uses only earlier outcomes and never includes test clients.
    refit=pd.concat([march_april,april_may],ignore_index=True)
    refit=refit[refit['client_hash_id'].isin(train_clients|validation_clients)].copy()
    assert set(refit['client_hash_id']).isdisjoint(test_clients)
    assert pd.to_datetime(refit['outcome_month']).max()<pd.Timestamp('2026-06-01')
    final_model=clone(model_candidates[selected]).fit(refit[FEATURES],refit['label'])
    test_features=feature_frames['2026-05'][feature_frames['2026-05']['client_hash_id'].isin(test_clients)].copy()
    # Score all eligible May pages before reading their future outcome.
    test_features['frozen_model_score']=final_model.predict_proba(test_features[FEATURES])[:,1]
    june=w.month('2026-06')
    test,flow_test=attach_labels(test_features,june,'2026-06')
    assert len(test)>=100 and test.label.nunique()==2
    test_scores={'momentum_rule':test['momentum_score'].to_numpy(),'volume_rule':test['volume_score'].to_numpy(),selected:test['frozen_model_score'].to_numpy()}
    test_metrics={name:evaluate(test,values) for name,values in test_scores.items()}
    cm=confusion_matrix(test['label'],test_scores[selected]>=.5,labels=[0,1])
    assert int(cm.sum())==len(test)
    # Show how much the global top 50 depends on a particular held-out client.
    loo=[]
    for group in sorted(test.client_hash_id.unique()):
        keep=test['client_hash_id'].ne(group).to_numpy()
        if keep.sum()<50:continue
        model_p=ranked_precision(test.label.to_numpy()[keep],test_scores[selected][keep],50)['expected']
        rule_p=ranked_precision(test.label.to_numpy()[keep],test_scores['momentum_rule'][keep],50)['expected']
        loo.append(model_p-rule_p)
    sensitivity={'method':'leave one held-out client out, fixed fitted model; descriptive, not a confidence interval',
                 'comparisons':len(loo),'minimum_p50_difference':float(min(loo)),'maximum_p50_difference':float(max(loo))}
    imputer=final_model.steps[0][1]
    importance_names=list(imputer.get_feature_names_out(FEATURES))
    fitted=final_model.steps[-1][1]
    if hasattr(fitted,'feature_importances_'):
        importance_values=fitted.feature_importances_;importance_kind='impurity importance in the final training fit'
    else:
        importance_values=np.abs(fitted.coef_[0]);importance_kind='absolute standardized coefficients, not causal effects'
    importance=[{'feature':name,'importance':float(value)} for name,value in sorted(zip(importance_names,importance_values),key=lambda x:x[1],reverse=True)[:8]]
    public_review=[]
    order_idx=np.argsort(-test_scores[selected],kind='stable')[:20]
    for rank,idx in enumerate(order_idx,1):
        row=test.iloc[idx]
        volume='500-999' if row['impressions']<1000 else '1,000-9,999' if row['impressions']<10000 else '10,000+'
        if pd.isna(row['weighted_position']):
            action,reason,caution='Check measurement','position_missing','Missing search context'
        elif row['ctr_pct']<.5 and row['weighted_position']<=20:
            action,reason,caution='Review snippet and intent','visible_low_ctr','Search layout may explain low CTR'
        elif row['half_month_change']<-.2:
            action,reason,caution='Inspect recent loss','past_momentum_drop','Seasonality or related pages may explain it'
        else:
            action,reason,caution='Inspect page and trend','model_review_candidate','Future decline is uncertain'
        public_review.append({'rank':rank,'score':round(float(test_scores[selected][idx]),3),'volume_band':volume,
                              'action':action,'reason':reason,'evidence':'Limited; uncalibrated score','what_could_be_wrong':caution})
    months['2026-06']=june
    scanned=w.quality
    receipt={'dataset':'FlyRank/internship-warehouse','revision':REVISION,'config':CONFIG,
             'source_sha256':source_hash,'run_utc':datetime.now(timezone.utc).isoformat(),
             'inventory':inventory,'scanned_months':scanned,'feature_filters':feature_flows,
             'cohort_clients':len(cohort_clients),'partition_clients':selection['client_partition_counts'],
             'train_rows':len(train),'validation_rows':len(validation),'refit_rows':len(refit),'test_rows':len(test),
             'train_positive_rate':float(train.label.mean()),'validation_positive_rate':float(validation.label.mean()),'test_positive_rate':float(test.label.mean()),
             'observed_train_clients':int(train.client_hash_id.nunique()),'observed_validation_clients':int(validation.client_hash_id.nunique()),'observed_test_clients':int(test.client_hash_id.nunique()),
             'outcome_coverage':{'March_to_April_all_clients':flow_train,'April_to_May_all_clients':flow_validation,'May_to_June_test_clients':flow_test},
             'selected_model':selected,'validation_preferred_method':recommended,'validation_metrics':val_metrics,'test_metrics':test_metrics,
             'final_model_errors_at_0_5':{'true_negative':int(cm[0,0]),'false_positive':int(cm[0,1]),'false_negative':int(cm[1,0]),'true_positive':int(cm[1,1])},
             'client_sensitivity':sensitivity,'importance_kind':importance_kind,'feature_importance':importance,
             'top20_review':public_review,'selection_receipt_file':'work/outputs/warehouse_selection_v2.json','selection_receipt_sha256':fingerprint(selection_path),'quality_revision':selection.get('quality_revision'),
             'first_selection_utc':selection['first_selection_utc'],
             'checks':{'disjoint_clients':True,'features_precede_outcomes':True,'train_only_imputation':True,
                       'daily_grain_unique_after_excluding_invalid_page_months':True,'tracking_gaps_not_filled_as_zero':True,'model_selected_before_june_read':True,
                       'no_label_or_id_features':True,'only_past_outcomes_in_final_fit':True},
             'limits':['outcome tracking coverage conditions evaluation','creation dates are snapshot metadata assumed historically stable',
                       'no historical publication or update-state reconstruction','only clients eligible in March','uncalibrated scores',
                       'one final time window; not causal refresh evaluation'],
             'versions':{'duckdb':duckdb.__version__}}
    dump(w.out/'warehouse_metrics.json',receipt)
    print('Warehouse final evaluation saved: '+format(len(test),',')+' pages on '+str(receipt['observed_test_clients'])+' held-out clients.',flush=True)
    w.con.close()
    return receipt

if __name__=='__main__':
    result=run_warehouse(Path(__file__).resolve().parents[2])
    print(json.dumps({'model':result['selected_model'],'test_rows':result['test_rows'],'test_positive_rate':result['test_positive_rate'],
                      'precision_at_50':{k:v['precision_at_50'] for k,v in result['test_metrics'].items()}},indent=2))
