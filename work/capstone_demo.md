### Five-minute demo
1. **0:00-0:45 - The question.** An editor has time for 20 to 50 pages. Explain the cost of a weak pick.
2. **0:45-1:30 - The data.** Show the starter and warehouse timing diagrams. Explain the difference between matching current decline and forecasting next-month decline.
3. **1:30-2:30 - The comparison.** Show the CSV baseline, warehouse momentum rule, and three warehouse client groups.
4. **2:30-3:45 - The result and errors.** Show both datasets, their own baselines, and their own base rates. The warehouse model has 80.0% Precision@50 versus 96.0% for the momentum rule.
5. **3:45-5:00 - The action and limits.** Walk through a row of the review list. Explain that a human checks the context, the score is not a recovery promise, and the completed warehouse test still covers only one final time window.

### Social-post cut
I worked on a simple content question: which pages should an editor review first? On a 30,000-page FlyRank starter sample, the strongest model found 37 declining pages among its first 50 picks, compared with 12 for the repo rule. I used held-out clients and checked the errors, but this is still a historical benchmark with overlapping time windows. I also built a warehouse forecast with separate months and clients: its final Precision@50 is 80.0% versus 96.0% for its momentum rule. The momentum rule won that forecast test. Each result has a different label and population; neither promises that a rewrite brings traffic back.

### Employer-facing summary
I built a reproducible content-review ranking study using 30,000 anonymized pages. It compares a transparent baseline with three models on held-out clients and reports 74% versus 24% Precision@50. A second experiment uses the Hugging Face warehouse to forecast next-month decline with separate training, validation, and final-test clients. The simple momentum rule outperformed the learned model on the final warehouse check (96% versus 80% Precision@50), so the recommendation follows that evidence. Both experiments are documented with their own baselines and limitations.
