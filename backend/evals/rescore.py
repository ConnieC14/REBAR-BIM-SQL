"""
Re-scores a finished run from its saved traces (no LLM calls).

    python -m evals.rescore evals/runs/<run> [evals/runs/<run2> ...]
"""
import os
import sys
from dotenv import load_dotenv

from evals.report import build_outputs
from evals.run import ENV_PATH, apply_config_env, load_config


def main():
    load_dotenv(ENV_PATH)
    for run_dir in sys.argv[1:]:
        # The run's own database / profile settings (the gold SQL is re-run)
        apply_config_env(load_config(os.path.join(run_dir, "config.yaml")))
        build_outputs(run_dir)


if __name__ == "__main__":
    main()
