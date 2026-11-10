"""
Evaluation harness for the agent pipelines.

Run from the backend/ directory:
    python -m evals.setup_fixtures                       # once: safety DB copy + restricted login
    python -m evals.run --config evals/configs/baseline_qwen7b.yaml
    python -m evals.rescore evals/runs/<run>
    python -m evals.compare evals/runs/<A> evals/runs/<B>
    python -m evals.dashboard evals/runs/<A> [evals/runs/<B> ...]
    python -m evals.review_suite wwi_dev
"""
