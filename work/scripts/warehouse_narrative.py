"""Plain-language warehouse sections and figures, rendered from computed receipts."""
import pandas as pd
import matplotlib.pyplot as plt

def add_warehouse_sections(wh,starter,section,table,figure,policy):
    model=wh['selected_model'];m=wh['test_metrics'][model];b=wh['test_metrics']['momentum_rule'];v=wh['test_metrics']['volume_rule']
    train_n=wh['observed_train_clients'];val_n=wh['observed_validation_clients'];test_n=wh['observed_test_clients']
    total_scan=sum(row['daily_rows'] for row in wh['scanned_months'].values())
    coverage=wh['outcome_coverage']['May_to_June_test_clients']
    source='https://huggingface.co/datasets/FlyRank/internship-warehouse/tree/'+wh['revision']
    inventory=pd.DataFrame([{'Month':month,'Daily rows':row['daily_rows'],'Page-month rows':row['page_months'],'Excluded duplicate page-months':row['excluded_duplicate_page_months']} for month,row in wh['scanned_months'].items()])
    section('Warehouse study: data and question',f"""
The starter experiment asks which pages resemble an already observed decline. I now ask a harder question: **can information from one month rank pages that will decline in the next month?** This brings the review list closer to a decision made before the outcome is known.

I use the [FlyRank warehouse release v20260703]({source}), pinned to its recorded revision. The full daily table has {wh['inventory']['daily_rows']:,} rows, from {wh['inventory']['start']} to {wh['inventory']['end']}. This experiment aggregates **{total_scan:,} daily rows from March through June 2026**. It does not train on every row in the full warehouse. Two small dimension-table extracts supply the client tracking start and content creation date.

{table(inventory)}

One model row is one eligible page at the end of a feature month. It must be at least 90 days old, have at least 500 impressions, and have usable search tracking for at least 90% of that month. The client's tracking must start on or before the first day of that month. I do not filter on current publication or deletion flags because they may describe a later state.

A tracking day is observed only when `gsc_data_available IS TRUE` and impressions and clicks are recorded. A measured zero stays zero; an unavailable day is not filled with zero. The cached summaries check the daily client-page-date grain before any features or labels are built. June contains 6,390 duplicate daily records in 355 page-months. The first evaluation stopped at that check, before computing June labels or metrics. The corrected quality policy excludes every affected page-month rather than guessing how to deduplicate it; the same rule is applied to all four months. The earlier model choice and validation results are preserved and checked against their original receipt. The cache keeps only the selected dimension fields and page-month summaries in ignored local Parquet files. No token or private IDs enter the paper.
""")
    filters=[]
    for month,row in wh['feature_filters'].items():
        filters.append({'Feature month':month,'Page-months':row['page_month_rows'],'Tracking started':row['history_started'],
                        '90% coverage':row['feature_tracking_90pct'],'90+ days old':row['age_90_days'],'500+ impressions':row['impressions_500']})
    section('Warehouse method: predict a later window',f"""
The label is 1 when **next-month impressions per observed day are more than 20% below feature-month impressions per observed day**. Dividing by observed days accounts for different month lengths and recorded exposure. I require 90% tracking coverage in the outcome month to evaluate the label; that conditions the result on measurable later history.

{table(pd.DataFrame(filters))}

The inputs are ten measurements from the feature month: logged impressions, logged clicks, CTR, impression-weighted position, the shares of days with impressions and clicks, daily impression variability, the change between the two half-month daily rates, tracking coverage, and age at month end. Half-month change is capped between -100% and +1,000% to limit extreme ratios. Undefined ratios remain missing, then receive a training-fitted median and a missingness flag. No outcome measurements or identifiers are model inputs.

I leave out current update dates, current content length, current publication state, GA4 activity, and the fixed-window query table. They are not needed for this first forecast test, and their timing or coverage would need additional work. Content creation dates come from the snapshot; I assume those dates are historically stable. That is a stated assumption, not a reconstructed history of every page.

**Two transparent baselines.** The momentum rule ranks pages by `max(0, -past_half_month_change) x log1p(month_impressions)`. It prioritizes a recent drop with visible demand. The volume rule simply ranks by feature-month impressions. These are different from the CSV's four-part baseline: its stale-content inputs do not have a reliable historical equivalent here.

I compare logistic regression, a depth-5 decision tree, and a 200-tree random forest with depth 8 and at least 50 rows per leaf. The tree also requires 50 rows per leaf. The models use class balancing and seed 42. Numeric filling, missingness flags, and logistic-regression scaling are fitted on training data only.

**Three separate groups of clients.** I shuffle the {wh['cohort_clients']} clients eligible in March once with seed 42 and assign approximately 60% to training, 20% to validation, and 20% to the final check. Training uses March features and April outcomes ({wh['train_rows']:,} pages; {train_n} observed clients). Validation uses April features and May outcomes ({wh['validation_rows']:,} pages; {val_n} observed clients). I select the model there, record the choice, then refit on {wh['refit_rows']:,} March-April and April-May page-periods from training and validation clients. Final evaluation uses May features and June outcomes from {test_n} clients excluded from both earlier groups.

I score the eligible May pages before loading June outcomes. Of {coverage['eligible_feature_pages']:,} eligible test candidates, {coverage['evaluable_pages']:,} have enough June tracking to evaluate and {coverage['unobserved_outcomes']:,} do not. The reported ranking metrics apply to the evaluable set. Reruns reproduce this recorded evaluation; they do not create a newly blind test each time.
""")
    fig,ax=plt.subplots(figsize=(11,4.1))
    for y,start,width,ostart,owidth in [(2,0,31,31,30),(1,31,30,61,31),(0,61,31,92,30)]:
        ax.broken_barh([(start,width)],(y,.55),facecolors='#1d4ed8')
        ax.broken_barh([(ostart,owidth)],(y,.55),facecolors='#b45309')
    ax.plot([],[],color='#1d4ed8',linewidth=8,label='Features available at month end')
    ax.plot([],[],color='#b45309',linewidth=8,label='Later outcome')
    ax.set(yticks=[.275,1.275,2.275],yticklabels=[f'Final check: {test_n} clients',f'Validation: {val_n} clients',f'Training: {train_n} clients'],
           xticks=[0,31,61,92,122],xticklabels=['1 March','1 April','1 May','1 June','1 July'],xlim=(0,122),ylim=(-.3,3.45),title='The warehouse test looks forward in time')
    ax.legend(loc='upper left',fontsize=10,ncol=2);ax.grid(axis='x',alpha=.2)
    figure('warehouse_windows','Figure 5. Feature and outcome months are separate. Final-test clients are excluded from training and validation; refitting uses only outcomes through May.')
    def comparison(metrics):
        return pd.DataFrame([{'Method':name.replace('_',' '),'P@20':r['precision_at_20'],'P@50':r['precision_at_50'],
                              'P@100':r['precision_at_100'],'ROC AUC':r['roc_auc'],'Average precision':r['average_precision']} for name,r in metrics.items()])
    section('Warehouse results: selection and final check',f"""
I chose **{model.replace('_',' ')}** as the strongest learned candidate using validation Precision@50, with average precision and ROC AUC breaking ties. Across rules and learned models, validation preferred **{wh['validation_preferred_method'].replace('_',' ')}**. This choice was recorded before June outcomes were read.

**April-to-May validation.** The declining rate is {wh['validation_positive_rate']:.1%} across {wh['validation_rows']:,} pages.

{table(comparison(wh['validation_metrics']))}

**May-to-June final check.** The declining rate is **{wh['test_positive_rate']:.1%} across {wh['test_rows']:,} pages**. The selected model has **{m['precision_at_50']:.1%} Precision@50**, compared with **{b['precision_at_50']:.1%} for the momentum rule** and **{v['precision_at_50']:.1%} for the volume rule**.

{table(comparison(wh['test_metrics']))}

The model-minus-momentum difference is {(m['precision_at_50']-b['precision_at_50'])*100:+.1f} percentage points at 50 review slots. Random ranking would average {wh['test_positive_rate']*50:.1f} declining pages per 50 picks. These results measure later decline, not the effect of an editorial change.

Ties are handled explicitly in this study: Precision@K is the expected result when ties at the cutoff are ordered randomly. For the selected model at K=50, the possible range from tied ordering is {m['ties_at_50']['minimum']:.1%} to {m['ties_at_50']['maximum']:.1%}. The receipt records these ranges for every method. This avoids giving a threshold rule or tree credit for an arbitrary file order.

As a simple robustness check, I remove one held-out client at a time without refitting. The model-minus-momentum Precision@50 difference ranges from {wh['client_sensitivity']['minimum_p50_difference']*100:+.1f} to {wh['client_sensitivity']['maximum_p50_difference']*100:+.1f} percentage points across {wh['client_sensitivity']['comparisons']} such checks. This is descriptive sensitivity, not a confidence interval or a significance test.
""")
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    data=[('Starter CSV: observed decline',['Repo rule','Random','Model'],[starter['baseline'],starter['base_rate'],starter['model']]),
          ('Warehouse: next-month decline',['Momentum','Volume','Random','Model'],[b['precision_at_50'],v['precision_at_50'],wh['test_positive_rate'],m['precision_at_50']])]
    for ax,(title,labels,values) in zip(axes,data):
        colors=['#64748b','#b45309','#1d4ed8'] if len(labels)==3 else ['#64748b','#087f8c','#b45309','#1d4ed8']
        ax.bar(labels,[100*x for x in values],color=colors,width=.6)
        for j,value in enumerate(values):ax.text(j,100*value+1.7,f'{value:.1%}',ha='center',fontsize=11,fontweight='bold')
        ax.set(ylim=(0,110),yticks=[0,20,40,60,80,100],ylabel='Precision@50 (%)',title=title)
    fig.tight_layout()
    figure('both_datasets', 'Figure 6. Each model is compared with baselines on its own evaluation set. The two panels use different populations, labels, features, and validation designs; their percentages are not a direct contest between datasets.')
    errors=wh['final_model_errors_at_0_5'];total=sum(errors.values());accuracy=(errors['true_positive']+errors['true_negative'])/total
    section('Warehouse interpretation and review guidance',f"""
At score 0.5, the selected model makes {errors['false_positive']:,} false-positive calls and misses {errors['false_negative']:,} declining pages. Its accuracy is {accuracy:.1%}; assigning every page to the majority class would give {max(wh['test_positive_rate'],1-wh['test_positive_rate']):.1%}. The other two counts are {errors['true_positive']:,} true positives and {errors['true_negative']:,} true negatives. The 0.5 cutoff is separate from a top-50 review budget.

The leading model inputs are {', '.join('`'+row['feature']+'`' for row in wh['feature_importance'][:3])}. Their recorded interpretation is {wh['importance_kind']}. These are descriptions of the fit, not proof that changing a feature will recover traffic.

For this warehouse task, I would start with the **momentum rule**. It led in validation and found 48 declining pages in the final top 50, compared with 40 for logistic regression. The rule is easier to explain and did better on this test; the learned model has not earned the extra work here. Check tracking and seasonality, compare related pages, and inspect the page before deciding whether a change is useful. The model's score is uncalibrated, and the review reasons are separate checks rather than causal explanations.

Below are the first five candidates in the **validation-preferred rule's** final-window demonstration. The [policy review receipt](outputs/warehouse_policy_review.json) contains all 20 with broad volume bands, suggested reviews, and reasons they could be wrong. The rule score is a ranking value, not a probability. These are generated review suggestions, not claims that I manually inspected the real pages.

{table(pd.DataFrame(policy['rows'][:5])[['rank','rule_score','volume_band','action','reason','what_could_be_wrong']])}
""")
    section('What the two datasets support',f"""
The CSV study reproduces the supplied benchmark: a model can match the current decline label more often than the four-part reference rule at the top of that list. Its overlapping windows and reused development holdout limit the claim.

The warehouse study tests a separate, forward-looking question. It fits preprocessing on earlier training rows, holds out whole clients, and evaluates a later outcome after recording model selection. On its final set, the model reaches {m['precision_at_50']:.1%} Precision@50, the momentum rule {b['precision_at_50']:.1%}, and the volume rule {v['precision_at_50']:.1%}, against a {wh['test_positive_rate']:.1%} base rate. The model wins the CSV comparison, but the simple momentum rule wins the warehouse forecast. That is the main practical finding. A different result from the CSV is not a contradiction: the question and candidate population changed.

Neither study measures the benefit of a refresh. The warehouse result also depends on reliable creation dates, March client eligibility, and sufficient tracking in the outcome month. Missing later outcomes are excluded, so this is not an evaluation of every page that a real editor would see. More client splits and later time windows would help establish whether the result holds.

[Warehouse metrics](outputs/warehouse_metrics.json) | [Recorded model choice](outputs/warehouse_selection_v2.json) | [Original pre-June choice](outputs/warehouse_selection_before_grain_fix.json) | [Warehouse analysis code](scripts/warehouse_capstone.py) | [Data inventory](outputs/warehouse_inventory.json)

The first warehouse run requires a saved Hugging Face read login with access to the gated release. The code reads only the selected columns, aggregates them, and reuses fingerprint-checked local caches on later runs. Its pinned revision and implementation follow [DuckDB's documented Hugging Face support](https://duckdb.org/docs/current/core_extensions/httpfs/hugging_face). Source dimensions, cache fingerprints, filters, model settings, and aggregate checks are recorded alongside the results.
""")
