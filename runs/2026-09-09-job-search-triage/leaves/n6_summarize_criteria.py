"""Leaf n6 - summarize_criteria."""


def summarize_criteria(assessments, criteria):
    diagnostics = []

    for criterion in criteria or []:
        criterion_id = criterion.get("id")
        counts = {"satisfied": 0, "not_satisfied": 0, "not_answerable": 0}
        not_answerable = []

        for assessment in assessments or []:
            for verdict in assessment.get("verdicts") or []:
                if verdict.get("criterion_id") != criterion_id:
                    continue
                outcome = verdict.get("outcome")
                if outcome in counts:
                    counts[outcome] += 1
                if outcome == "not_answerable":
                    not_answerable.append(
                        {
                            "source_id": assessment.get("source_id"),
                            "source_posting_id": assessment.get("source_posting_id"),
                        }
                    )

        diagnostics.append(
            {
                "criterion_id": criterion_id,
                "discriminated": counts["satisfied"] > 0 and counts["not_satisfied"] > 0,
                "outcome_counts": counts,
                "not_answerable_posting_ids": not_answerable,
            }
        )

    return diagnostics
