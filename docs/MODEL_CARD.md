# Model card

## Deployed model

`raw_yelpchi_inductive_roberta_gnn_v1`, run `raw_yelpchi_inductive_seed42_20261025T125837Z`, is the current CSV scoring model. It combines frozen `FacebookAI/roberta-base` embeddings, 14 numeric features and three relation-specific GraphSAGE branches with text-conditioned attention and gated fusion. The model is an investigation aid, not a fraud adjudicator.

## Data and evaluation

The exact labelled source is `samygithub/collective-opinion-spam-detection/training_data.csv`, SHA-256 `dbd3769b608bf249ed484f87d291e5d73f4988fd33e26f1bb96a50e8cdd418c8`. It contains 47,176 historical reviews: 6,243 Y/spam labels and 40,933 N/nonspam labels. The source's `rating_OhNo` column is explicitly mapped to rating. Yelp filtering supplies imperfect reference labels.

After sorting by date and review ID: train 28,305, validation 9,435, test 9,436. The downloaded 20,219-row `testing_data.csv` has no labels and is excluded from measured supervised metrics. The model checkpoint and threshold were selected using validation macro F1. Test ROC-AUC is 0.8105, macro F1 0.6624 and average precision 0.4211. ROC-AUC is not ordinary accuracy.

## Inputs and training

RoBERTa revision `e2da8e2f811d1448a5b465c236feacd80ffbac7b` is frozen, with masked-mean pooling and 192-token truncation. Numeric features describe rating, earlier reviewer/product activity, text length/style and cyclic month/weekday. Scaling is fitted on training rows only. Graph inputs contain no labels.

RUR connects the same reviewer; RSR the same product and rating; RTR the same product within 30 days. Directed earlier-to-later relations use at most 50 recent neighbors each. Hidden width 128, dropout 0.2, AdamW learning rate 0.001, weight decay 0.0001, train-class-weighted cross entropy, maximum 80 epochs, patience 12. The deployed run completed 80 epochs and selected epoch 74.

Every text-enabled run in the matched comparison reached the 80-epoch cap (one full-batch gradient update per epoch). Only graph-only stopped early. Results compare a fixed training budget, not confirmed convergence, and can reflect convergence-speed differences.

## Decisions and evidence

Scores at or above 0.7870707071 are flagged. This validation-selected cutoff is not universally optimal. Scores are not separately probability-calibrated; 0.9 does not establish 90% fraud probability. A cleared result is below the cutoff, not proven genuine. Saved relation attention and neighbors support inspection but are not causal proof of fraud.

At that cutoff the recorded test confusion matrix is TP 553, FP 834, TN 7,351, FN 698: flag precision is about 39.9% and spam recall about 44.2%. ROC-AUC 0.8105 does not imply that most flagged rows are necessarily spam. When spam is rarer, precision can fall further even if true/false-positive rates stayed constant; those rates are not proven to transfer to new domains. The UI therefore prioritizes human review and does not estimate file accuracy without independent labels.

Relation weights are a three-way gate across relation branches, not attention over individual neighbors. The interface suppresses weights for zero-neighbor relations without renormalizing or changing the actual inference result.

Manifest checks and fixed-review reproduction reject missing or mismatched artifacts. Human feedback is stored separately and does not automatically retrain the model or erase an old prediction.

## Controlled comparison

The [matched benchmark](benchmarks/README.md) uses this checkpoint as its seed-42 NeuroGraph arm and adds architecture baselines and seeds 43/44 on the same split. The [historical run records](runs/) use different representations/protocols and are not ranked as a fair three-way comparison.

## Limitations

The existing holdout is reused for a retrospective comparison. Day-level timestamps and review-ID tie-breaking define replay order, not verified within-day arrival time. The modality comparison does not separately isolate link contribution from numeric features. Three seeds measure initialization variation on one split, not independent data uncertainty. Historical Yelp labels are imperfect and domain transfer to current e-commerce or AI-written reviews is unverified. Long reviews are truncated. Replay includes earlier unlabelled arrivals; live snapshots/batches can provide less context. Uploaded files without true labels have predictions but no measured accuracy. Missing-context edge removal tests sensitivity, not demonstrated resistance to real attacks.
