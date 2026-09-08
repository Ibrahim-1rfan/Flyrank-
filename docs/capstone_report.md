# Which pages should I review first for a content refresh?

**Ibrahim Irfan Nazar | Refresh / Content Opportunity Scoring**

## Title + Abstract

Which mature pages should a content team review first when it has only 20 to 50 slots? I studied both the 30,000-page starter CSV and a separate monthly forecast built from the Hugging Face warehouse. The CSV comparison uses held-out clients with an overlapping historical label, while the warehouse keeps feature months before outcome months and reserves separate clients for its final May-to-June check. The CSV model reaches 74% Precision@50 versus 24% for its reference rule, and the warehouse model reaches 80.0% versus 96.0% for its momentum rule, with base rates of 39.1% and 31.1%, respectively. The model wins the CSV comparison while the simple momentum rule wins the warehouse forecast, and neither experiment proves that a refresh will recover traffic.

## Introduction / Problem statement

### Starter CSV: problem framing

I want to help a content team decide which 20 to 50 mature pages to inspect first each month. One row is one page, and the output is a ranked review list. An editor still checks the page, its purpose, and recent changes before deciding what to edit.

In this starter sample, 16,262 of 30,000 pages (54.2%) have the declining label. Of those, 8,031 have at least 1,000 impressions over 90 days. That is too many pages to inspect one by one. A poor pick uses time on a page that may not need work; a missed pick can leave a useful page unattended.

This is a ranking exercise. It measures how often the first picks match observed decline. It does not measure traffic recovered, money saved, or the benefit of a rewrite.

### Warehouse: the question

The starter experiment asks which pages resemble an already observed decline. I now ask a harder question: **can information from one month rank pages that will decline in the next month?** This brings the review list closer to a decision made before the outcome is known.

## Data

### Starter CSV: data and safety

I use the bundled `data/raw/content_refresh_anonymized.csv`: 30,000 rows, 44 columns, and 32 pseudonymized clients. Search and engagement measurements cover a trailing 90-day window. The supplied CSV does not record exact calendar start and end dates, so I do not assign the warehouse release dates to it.

The reference filter keeps pages with at least one impression and age of at least 90 days, then removes duplicate page IDs. All 30,000 rows pass. Unlike my week-2 candidate filter, this comparison retains pages with unavailable position to match the supplied capstone benchmark.

| Measurement | Pages |
| --- | --- |
| Word count missing | 7699 |
| Search-volume estimate missing | 2468 |
| Position unavailable (zero) | 1205 |

Missing word count is not proof of short content. Position zero means no position measurement. Rates such as CTR are already percentages: 0.5 means 0.5%. Scroll rate and AI traffic share can exceed 100 because of their measurement definitions.

Page and client IDs are used only for joining, checking uniqueness, and splitting. The report contains aggregates and broad review bands, with no client names, page addresses, raw queries, or pseudonymous ID values. Numeric keyword context is allowed; keyword text is absent. The file fingerprint and exact package versions are in the metrics receipt.

### Warehouse: release, tables, and eligibility

I use the [FlyRank warehouse release v20260703](https://huggingface.co/datasets/FlyRank/internship-warehouse/tree/50cbf7c3909d07be4d1b5906b4d09e882e5acbf2), pinned to its recorded revision. The full daily table has 78,835,655 rows, from 2025-01-27 to 2026-06-30. This experiment aggregates **43,647,556 daily rows from March through June 2026**. It does not train on every row in the full warehouse. Two small dimension-table extracts supply the client tracking start and content creation date.

| Month | Daily rows | Page-month rows | Excluded duplicate page-months |
| --- | --- | --- | --- |
| 2026-03 | 9841378 | 331437 | 0 |
| 2026-04 | 10424730 | 362172 | 0 |
| 2026-05 | 11687376 | 389153 | 0 |
| 2026-06 | 11694072 | 409205 | 355 |

One model row is one eligible page at the end of a feature month. It must be at least 90 days old, have at least 500 impressions, and have usable search tracking for at least 90% of that month. The client's tracking must start on or before the first day of that month. I do not filter on current publication or deletion flags because they may describe a later state.

| Feature month | Page-months | Tracking started | 90% coverage | 90+ days old | 500+ impressions |
| --- | --- | --- | --- | --- | --- |
| 2026-03 | 331437 | 322135 | 83842 | 64624 | 41512 |
| 2026-04 | 362172 | 350708 | 93265 | 71454 | 43644 |
| 2026-05 | 389153 | 377273 | 97109 | 76161 | 43695 |

A tracking day is observed only when `gsc_data_available IS TRUE` and impressions and clicks are recorded. A measured zero stays zero; an unavailable day is not filled with zero. The cached summaries check the daily client-page-date grain before any features or labels are built. June contains 6,390 duplicate daily records in 355 page-months. The first evaluation stopped at that check, before computing June labels or metrics. The corrected quality policy excludes every affected page-month rather than guessing how to deduplicate it; the same rule is applied to all four months. The earlier model choice and validation results are preserved and checked against their original receipt. The cache keeps only the selected dimension fields and page-month summaries in ignored local Parquet files. No token or private IDs enter the paper.

I leave out current update dates, current content length, current publication state, GA4 activity, and the fixed-window query table. They are not needed for this first forecast test, and their timing or coverage would need additional work. Content creation dates come from the snapshot; I assume those dates are historically stable. That is a stated assumption, not a reconstructed history of every page.

## Methodology

### Earlier work: what changed my thinking

In week 1, I settled on refresh review because the declining-page count was large. In week 2, I tried a stale-and-visible rule and small decision trees. The useful lesson was to compare actual results, rather than assume the more complex method would win.

In weeks 3 and 4, I explored the March 2026 warehouse partition using daily search facts and content metadata. The saved outputs report 9,841,378 daily rows, 61,863 filtered pages, a 38.3% declining rate, and Precision@20 of 10.0%. These are historical notebook outputs, not numbers recomputed by this capstone. One later output says 10 wrong picks out of 20; 10% precision would imply 18 wrong picks. Those saved cells are inconsistent, so I do not use them as a verified result or mix them with the starter benchmark.

There is also a method issue worth keeping visible. Those March features use the full month, including the second half that defines the label. Removing the named future-impressions column does not remove that overlap. The label compares 15 days with 16 days, and current metadata may not describe what was known halfway through March. Weak score-label correlation cannot certify that a feature is safe. An average position outside the first page also cannot establish that position has fallen.

A future warehouse experiment should use features and eligible pages defined before the outcome, comparable exposure windows, and metadata known at the decision date. June was intended as a later test month in my earlier work; the warehouse extension below now evaluates a separately designed May-to-June forecast after model selection.

### Starter CSV: baseline

The reference rule combines four things: visibility (40%), time since update (30%), position opportunity (25%), and a word-count gap (5%). It uses no fitted weights. Both it and the models are scored on exactly the same held-out pages and labels.

Visibility and freshness are percentile ranks across this fixed sample. Position opportunity gives more weight to a measured position closer to the top, multiplied by visibility. The word-count gap is the inverse word-count percentile, also multiplied by visibility. These are simple priorities, not established causes of decline. The full formulas are in the notebook.

My earlier rule is `stale x visible x impressions`. It produces 17 positive scores across the sample and 0 on the held-out clients. With no eligible held-out pages, every score there ties at zero. An arbitrary top 50 would measure file ordering, so I report no meaningful Precision@50 for that rule. Random tie-breaking would average the held-out declining rate (39.1%). This rule needs review before it could serve that group.

For an exact reference comparison, the baseline percentiles and category vocabulary use the full sample, as the original pipeline does. No held-out labels enter fitting, but this is not a fully independent preprocessing test. A stricter deployment experiment would learn those transformations on training data only.

![Figure 1. These are fixed policy weights, not learned effects or a measure of traffic recovery.](figures/baseline_weights.svg)

*Figure 1. These are fixed policy weights, not learned effects or a measure of traffic recovery.*

### Starter CSV: methodology and model

The target is `is_declining_label = (trend_direction == 'down')`. The data dictionary defines down as a fall of more than 20% in last-30-day impressions relative to the preceding 30 days. This is a rule-based summary of observed traffic, not a label saying that an editor should rewrite a page.

I compare logistic regression, a depth-5 decision tree, and a random forest with 200 trees, depth 10, and at least 25 rows per leaf. The decision tree has at least 50 rows per leaf. The models use class balancing; logistic regression standardizes its inputs using training rows. Seed 42 fixes the client shuffle and model randomness.

**Numeric inputs (18):** `search_volume`, `competition`, `cpc`, `word_count`, `char_count`, `log_impressions_90d`, `log_clicks_90d`, `log_sessions_90d`, `log_ai_sessions_90d`, `days_with_impressions`, `days_with_sessions`, `content_age_days`, `days_since_last_update`, `ctr`, `avg_position`, `engagement_rate`, `scroll_rate`, `ai_traffic_pct`.

**Categorical inputs (8):** `competition_level`, `content_type`, `main_intent`, `age_tier`, `freshness_tier`, `word_count_tier`, `impression_tier`, `position_tier`.

These become 52 encoded model columns. The reference preparation fills numeric gaps with zero and missing categories with `unknown`; it logs four traffic totals with `log1p`. I retain this policy to reproduce the benchmark, but zero can mix missing measurements with real zeros. Missingness indicators and training-only imputation are useful next checks, not improvements measured here.

Direct trend fields, the six 30-day comparison inputs, IDs, provider/model metadata, and product scores are excluded from model inputs. That check does not establish temporal independence: the retained 90-day totals overlap the recent label window.

The split holds out 6 of 32 whole clients: 27,675 training pages and 2,325 held-out pages. It is about 20% of clients, not 20% of pages. I compare candidates by Precision@50 on this same split, so it is a development holdout used for selection. It is not an untouched final test, and it does not test future months.

![Figure 2. The last two windows define observed decline. Their overlap with model inputs rules out a future-prediction claim.](figures/time_windows.svg)

*Figure 2. The last two windows define observed decline. Their overlap with model inputs rules out a future-prediction claim.*

### Warehouse: predict a later window

The label is 1 when **next-month impressions per observed day are more than 20% below feature-month impressions per observed day**. Dividing by observed days accounts for different month lengths and recorded exposure. I require 90% tracking coverage in the outcome month to evaluate the label; that conditions the result on measurable later history.

The inputs are ten measurements from the feature month: logged impressions, logged clicks, CTR, impression-weighted position, the shares of days with impressions and clicks, daily impression variability, the change between the two half-month daily rates, tracking coverage, and age at month end. Half-month change is capped between -100% and +1,000% to limit extreme ratios. Undefined ratios remain missing, then receive a training-fitted median and a missingness flag. No outcome measurements or identifiers are model inputs.

**Two transparent baselines.** The momentum rule ranks pages by `max(0, -past_half_month_change) x log1p(month_impressions)`. It prioritizes a recent drop with visible demand. The volume rule simply ranks by feature-month impressions. These are different from the CSV's four-part baseline: its stale-content inputs do not have a reliable historical equivalent here.

I compare logistic regression, a depth-5 decision tree, and a 200-tree random forest with depth 8 and at least 50 rows per leaf. The tree also requires 50 rows per leaf. The models use class balancing and seed 42. Numeric filling, missingness flags, and logistic-regression scaling are fitted on training data only.

**Three separate groups of clients.** I shuffle the 28 clients eligible in March once with seed 42 and assign approximately 60% to training, 20% to validation, and 20% to the final check. Training uses March features and April outcomes (32,771 pages; 16 observed clients). Validation uses April features and May outcomes (1,373 pages; 6 observed clients). I select the model there, record the choice, then refit on 69,474 March-April and April-May page-periods from training and validation clients. Final evaluation uses May features and June outcomes from 6 clients excluded from both earlier groups.

I score the eligible May pages before loading June outcomes. Of 5,886 eligible test candidates, 5,696 have enough June tracking to evaluate and 190 do not. The reported ranking metrics apply to the evaluable set. Reruns reproduce this recorded evaluation; they do not create a newly blind test each time.

![Figure 5. Feature and outcome months are separate. Final-test clients are excluded from training and validation; refitting uses only outcomes through May.](figures/warehouse_windows.svg)

*Figure 5. Feature and outcome months are separate. Final-test clients are excluded from training and validation; refitting uses only outcomes through May.*

## Results

### Starter CSV: results and evaluation

The strongest candidate in this run is **random forest**. It finds **37 declining pages in its first 50 picks**, compared with **12 for the reference rule**. That is 25 additional matches to the historical label, or 50.0 percentage points in Precision@50.

| Method | P@20 | P@50 | P@100 | ROC AUC | Average precision |
| --- | --- | --- | --- | --- | --- |
| baseline rules | 0.150 | 0.240 | 0.360 | 0.627 | 0.468 |
| logistic regression | 0.350 | 0.400 | 0.440 | 0.700 | 0.522 |
| decision tree | 0.550 | 0.620 | 0.600 | 0.742 | 0.575 |
| random forest | 0.650 | 0.740 | 0.720 | 0.750 | 0.618 |

The held-out declining rate is **39.1% (909/2,325)**. Random selection would average 19.5 declining pages in 50 picks; this is an expectation, not another trained model. The majority class is not declining, giving **60.9%** accuracy if every page is assigned that class. The full sample declining rate of 54.2% belongs to a different population.

The supplied metrics file recorded random-forest Precision@50 of 74% and baseline Precision@50 of 24%. I preserve that original receipt and report the fresh values above. The reference ranking helper uses pandas score sorting. A shallow tree has many tied scores, so its top-K result can change with ordering or library versions even when ROC AUC is unchanged. For this run, the tree's top-50 precision can range from 2.0% to 98.0% across valid orders of the boundary ties. The metrics receipt records tie bounds for each method.

This is one grouped development comparison. I have not measured uncertainty across repeated client splits, and I do not claim that the observed margin is statistically significant.

![Figure 3. All methods use the same 2,325 held-out pages. The random line is their 39.1% declining rate; connected points summarize K=20, 50, and 100 only.](figures/precision_comparison.svg)

*Figure 3. All methods use the same 2,325 held-out pages. The random line is their 39.1% declining rate; connected points summarize K=20, 50, and 100 only.*

### Starter CSV: interpretation and errors

The model's top three importance entries are `days_with_impressions`, `log_impressions_90d`, `avg_position`. These describe the measurements the model used to separate pages in this sample. Their importance is an internal model summary, not evidence that editing one feature changes traffic. Correlated measurements and missing-data patterns can divide or inflate importance.

At the ordinary 0.5 score cutoff, the selected model has 676 true positives, 887 true negatives, 529 false positives, and 233 false negatives. Recall is 74.4%; accuracy is 67.2%, compared with 60.9% majority-class accuracy. This threshold result is separate from choosing the top 50.

| Impressions in 90 days | Pages | Declining rate | False positives | False negatives |
| --- | --- | --- | --- | --- |
| Under 100 | 1430 | 0.300 | 148 | 225 |
| 500-999 | 141 | 0.574 | 60 | 0 |
| 1,000+ | 477 | 0.503 | 204 | 6 |
| 100-499 | 277 | 0.574 | 117 | 2 |

Even at the top of the ranking, 13 of the first 50 picks do not have the declining label. Those are weaker matches to this proxy, not proof that the pages have no editorial value. The false negatives show why the list should not be the only way a team notices problems.

![Figure 4. Errors use held-out predictions. Importance comes from the same training fit; neither panel measures the impact of a refresh.](figures/errors_and_features.svg)

*Figure 4. Errors use held-out predictions. Importance comes from the same training fit; neither panel measures the impact of a refresh.*

### Warehouse: selection and final check

I chose **logistic regression** as the strongest learned candidate using validation Precision@50, with average precision and ROC AUC breaking ties. Across rules and learned models, validation preferred **momentum rule**. This choice was recorded before June outcomes were read.

**April-to-May validation.** The declining rate is 56.7% across 1,373 pages.

| Method | P@20 | P@50 | P@100 | ROC AUC | Average precision |
| --- | --- | --- | --- | --- | --- |
| momentum rule | 0.950 | 0.880 | 0.920 | 0.704 | 0.756 |
| volume rule | 0.350 | 0.340 | 0.430 | 0.471 | 0.530 |
| logistic regression | 0.850 | 0.840 | 0.850 | 0.769 | 0.786 |
| decision tree | 0.456 | 0.456 | 0.590 | 0.685 | 0.673 |
| random forest | 0.850 | 0.840 | 0.840 | 0.743 | 0.768 |

**May-to-June final check.** The declining rate is **31.1% across 5,696 pages**. The selected model has **80.0% Precision@50**, compared with **96.0% for the momentum rule** and **26.0% for the volume rule**.

| Method | P@20 | P@50 | P@100 | ROC AUC | Average precision |
| --- | --- | --- | --- | --- | --- |
| momentum rule | 1.000 | 0.960 | 0.940 | 0.700 | 0.556 |
| volume rule | 0.250 | 0.260 | 0.280 | 0.462 | 0.290 |
| logistic regression | 0.850 | 0.800 | 0.800 | 0.680 | 0.505 |

The model-minus-momentum difference is -16.0 percentage points at 50 review slots. Random ranking would average 15.5 declining pages per 50 picks. These results measure later decline, not the effect of an editorial change.

Ties are handled explicitly in this study: Precision@K is the expected result when ties at the cutoff are ordered randomly. For the selected model at K=50, the possible range from tied ordering is 80.0% to 80.0%. The receipt records these ranges for every method. This avoids giving a threshold rule or tree credit for an arbitrary file order.

As a simple robustness check, I remove one held-out client at a time without refitting. The model-minus-momentum Precision@50 difference ranges from -16.0 to +0.0 percentage points across 6 such checks. This is descriptive sensitivity, not a confidence interval or a significance test.

![Figure 6. Each model is compared with baselines on its own evaluation set. The two panels use different populations, labels, features, and validation designs; their percentages are not a direct contest between datasets.](figures/both_datasets.svg)

*Figure 6. Each model is compared with baselines on its own evaluation set. The two panels use different populations, labels, features, and validation designs; their percentages are not a direct contest between datasets.*

### Warehouse: interpretation and errors

At score 0.5, the selected model makes 539 false-positive calls and misses 1,155 declining pages. Its accuracy is 70.3%; assigning every page to the majority class would give 68.9%. The other two counts are 615 true positives and 3,387 true negatives. The 0.5 cutoff is separate from a top-50 review budget.

The leading model inputs are `half_month_change`, `daily_impression_cv`, `log_impressions`. Their recorded interpretation is absolute standardized coefficients, not causal effects. These are descriptions of the fit, not proof that changing a feature will recover traffic.

### What the two datasets support

The CSV study reproduces the supplied benchmark: a model can match the current decline label more often than the four-part reference rule at the top of that list. Its overlapping windows and reused development holdout limit the claim.

The warehouse study tests a separate, forward-looking question. It fits preprocessing on earlier training rows, holds out whole clients, and evaluates a later outcome after recording model selection. On its final set, the model reaches 80.0% Precision@50, the momentum rule 96.0%, and the volume rule 26.0%, against a 31.1% base rate. The model wins the CSV comparison, but the simple momentum rule wins the warehouse forecast. That is the main practical finding. A different result from the CSV is not a contradiction: the question and candidate population changed.

## Limitations & honest framing

### Limitations and next checks

**The CSV study is a starter-snapshot benchmark.** It supports a comparison on the supplied 30,000 pages, not a result on the full warehouse or on future traffic. The actual declining label is already available at the snapshot; the model's value here is as a ranking experiment, not as a way to discover otherwise unknown decline.

**The outcome is a proxy.** Decline does not establish a need for a rewrite or likely recovery. Seasonality, tracking changes, competition, and consolidation can look similar in these aggregates. Pages with no exposure or age below 90 days are outside the sample.

**The CSV development holdout has been used to compare models.** There is no untouched final test or measured interval across repeated client splits. Only six clients are held out, their sizes differ, and the positive rate differs from the full sample. Results should not be generalized to every client.

**The CSV preprocessing has known weaknesses.** The reproduced benchmark uses full-sample percentiles and category vocabulary, zero-filled numeric gaps, and same-window traffic inputs. These choices are disclosed rather than described as a complete leakage pass. The identifier and direct-target checks cover only those specific risks.

**The action guidance has not been tested in production.** Scores are uncalibrated and evidence labels are heuristic. The saved March warehouse outputs need a clean rerun after correcting window overlap and equalizing exposure periods. The new warehouse experiment corrects those timing problems for a new monthly forecast; it does not validate the old March scores. The warehouse has separate client groups and a later final window, but it still assumes stable creation dates, uses one final period, and excludes insufficiently observed outcomes. Publishing and causal traffic recovery have not been demonstrated.

### What the two datasets cannot establish

Neither study measures the benefit of a refresh. The warehouse result also depends on reliable creation dates, March client eligibility, and sufficient tracking in the outcome month. Missing later outcomes are excluded, so this is not an evaluation of every page that a real editor would see. More client splits and later time windows would help establish whether the result holds.

## Ranked recommendations

### Starter CSV: ranked recommendations

I would start with the model ranking, then use the evidence to choose the review. The score orders pages by resemblance to observed decline; it is not a calibrated probability that a rewrite will work. Reason codes are separate editorial checks, not explanations of individual model decisions.

1. **Check the measurement.** Confirm tracking and enough impressions before treating a dip as a content problem.
2. **Review the first 20 candidates.** Check the traffic history, related pages, seasonality, page accuracy, and search intent. For a visible page with low CTR, inspect the search snippet and intent match first. Low CTR alone does not establish that the title is wrong.
3. **Make the smallest justified change.** Record why the editor accepts or rejects the suggestion. Age or word count alone is not a reason to rewrite, expand, merge, or prune.
4. **Measure what happens next.** Record review time and later outcomes. A comparison group or controlled test would be needed to estimate the effect of acting on the list.

The first 20 held-out candidates below retain only rank, model score, broad volume bands, and review guidance. Evidence labels describe available context, not statistical confidence. No new row-level dataset is exported.

| Rank | Model score | Impressions band | Review action | Reason | Evidence | What could make it wrong |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.768 | 500-999 | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 2 | 0.763 | 1,000+ | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 3 | 0.763 | 100-499 | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 4 | 0.754 | 500-999 | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 5 | 0.753 | 100-499 | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 6 | 0.750 | 500-999 | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 7 | 0.742 | 1,000+ | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 8 | 0.740 | 1,000+ | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 9 | 0.739 | 500-999 | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 10 | 0.739 | 100-499 | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 11 | 0.737 | 1,000+ | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 12 | 0.735 | 1,000+ | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 13 | 0.735 | 1,000+ | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 14 | 0.734 | 1,000+ | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 15 | 0.733 | 100-499 | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 16 | 0.732 | 1,000+ | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 17 | 0.731 | 500-999 | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |
| 18 | 0.731 | 500-999 | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 19 | 0.730 | 1,000+ | Review snippet and intent | visible_low_ctr | More context | Search layout or intent may explain low CTR |
| 20 | 0.729 | 100-499 | Inspect the trend and page | model_review_candidate | Limited | Seasonality or related pages may explain the drop |

The reference pipeline also exports a full-data queue that blends 70% model score with 30% normalized baseline. That is a different ranking, fitted after evaluation. Its performance cannot be assumed to equal the model-only figures in this paper, so I do not use it as my evaluated output.

### Warehouse: review guidance

For this warehouse task, I would start with the **momentum rule**. It led in validation and found 48 declining pages in the final top 50, compared with 40 for logistic regression. The rule is easier to explain and did better on this test; the learned model has not earned the extra work here. Check tracking and seasonality, compare related pages, and inspect the page before deciding whether a change is useful. The model's score is uncalibrated, and the review reasons are separate checks rather than causal explanations.

Below are the first five candidates in the **validation-preferred rule's** final-window demonstration. The [policy review receipt](outputs/warehouse_policy_review.json) contains all 20 with broad volume bands, suggested reviews, and reasons they could be wrong. The rule score is a ranking value, not a probability. These are generated review suggestions, not claims that I manually inspected the real pages.

| rank | rule_score | volume_band | action | reason | what_could_be_wrong |
| --- | --- | --- | --- | --- | --- |
| 1 | 10.153 | 10,000+ | Review recent loss, snippet, and intent | past_decline_and_low_ctr | Seasonality, tracking changes, or related-page gains |
| 2 | 9.938 | 10,000+ | Review recent loss, snippet, and intent | past_decline_and_low_ctr | Seasonality, tracking changes, or related-page gains |
| 3 | 9.833 | 10,000+ | Review recent loss, snippet, and intent | past_decline_and_low_ctr | Seasonality, tracking changes, or related-page gains |
| 4 | 9.493 | 10,000+ | Review recent loss, snippet, and intent | past_decline_and_low_ctr | Seasonality, tracking changes, or related-page gains |
| 5 | 9.191 | 10,000+ | Review recent loss, snippet, and intent | past_decline_and_low_ctr | Seasonality, tracking changes, or related-page gains |

## Reproducibility

### Notebook, repository, and rerun instructions

[Repository](https://github.com/Ibrahim-1rfan/Flyrank-) | [Capstone notebook](notebooks/capstone.ipynb) | [Fresh metrics](outputs/capstone_metrics.json) | [Original supplied metrics](outputs/capstone_metrics_original.json)

The experiment uses the bundled starter file and seed 42. The CSV portion needs no login. The first warehouse run needs a saved Hugging Face read login (`hf auth login`) and access to `FlyRank/internship-warehouse`; later runs reuse local caches. From a fresh clone, run:

```text
python -m pip install -r requirements.txt
python -m pip install -r work/requirements-capstone.txt
python work/scripts/run_capstone.py
```

Or open `work/notebooks/capstone.ipynb` in Jupyter and run all cells. The notebook builds the features and held-out frame, runs both experiments, computes every result, and writes this paper. Keep the full `work/` layout when sharing the HTML so its notebook and metrics links resolve. Charts and styles are embedded in the HTML itself, so the paper also opens offline as one file.

This run uses: python 3.10.11, numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, matplotlib 3.8.4. Direct analysis and notebook dependencies are pinned in `work/requirements-capstone.txt`. The metrics include a SHA-256 fingerprint of the input, the notebook code, the imported reference helpers, and the paper builder. Top-K scores with ties can vary across stacks; the receipt records their possible boundary range.

The delivered artifact is a local HTML paper. The internship also asks for a deployed page and its direct address in `submission/paper_url.txt`; a generated file alone does not establish publication.

### Warehouse: recorded choices and cached data

[Warehouse metrics](outputs/warehouse_metrics.json) | [Recorded model choice](outputs/warehouse_selection_v2.json) | [Original pre-June choice](outputs/warehouse_selection_before_grain_fix.json) | [Warehouse analysis code](scripts/warehouse_capstone.py) | [Data inventory](outputs/warehouse_inventory.json)

The first warehouse run requires a saved Hugging Face read login with access to the gated release. The code reads only the selected columns, aggregates them, and reuses fingerprint-checked local caches on later runs. Its pinned revision and implementation follow [DuckDB's documented Hugging Face support](https://duckdb.org/docs/current/core_extensions/httpfs/hugging_face). Source dimensions, cache fingerprints, filters, model settings, and aggregate checks are recorded alongside the results.

## Acknowledgments & data credit

[Built on the FlyRank ML Internship dataset](https://flyrank.ai).

I used the repository's data dictionary, starter scripts, and capstone template, alongside my earlier assignment notebooks. AI assistance helped review the code and simplify the writing; the reported results are computed by this notebook. The checks support the stated benchmark, while the remaining limits stay visible.
