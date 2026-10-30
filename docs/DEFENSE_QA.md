# Project review questions

The [beginner viva guide](defense/BEGINNER_VIVA_GUIDE.md) explains the dataset, models, metrics, databases, roles and deployment in plain language.

## Why can we compare the four models now

They share the same 47,176 real review identities, chronological train/validation/test membership, allowed relationship construction, frozen text embeddings where applicable, optimization budget and validation-selection objective. The architectures deliberately differ in whether and how they use text and graph information. The test contains the same 9,436 reviews for every arm.

## Why are historical results different

The structured MAT run uses 45,954 nodes and 32 supplied features. The earlier raw multimodal run uses a fixed known-node graph and a random stratified split. Those records remain visible as historical evidence, outside the new matched ranking. The deployed seed-42 checkpoint is reproduced and included in the matched comparison.

## Do the results prove NeuroGraph is always best

No. Report the observed winner for each metric and selected seed or three-seed mean. Standard deviation measures training variation, not a confidence interval. One existing chronological holdout and imperfect Yelp filtering labels do not establish universal superiority or accuracy on an unlabelled customer file.

## What happened to the near-perfect prototype scores

The older 5,000-node fixture generated features and graph links using labels. Those values were synthetic pipeline checks and cannot establish real-data fraud detection performance. The current comparison uses the verified raw dataset and explicitly label-free model inputs.
