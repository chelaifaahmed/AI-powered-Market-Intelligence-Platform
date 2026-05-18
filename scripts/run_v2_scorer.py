"""Run the V2 opportunity scorer.

Idempotent — safe to re-run; existing v2_* columns are overwritten.

Usage:
    python -m scripts.run_v2_scorer
"""
import logging
import sys
import os

# Ensure project root is on the path regardless of how the script is invoked
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from database.connection import get_db_session
from analytics.v2_opportunity_scorer import V2Scorer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_v2_scorer")


def main() -> None:
    logger.info("Starting V2 opportunity scorer…")
    with get_db_session() as session:
        scorer = V2Scorer(session)
        scorer.run()
        session.commit()
    logger.info("Done.")
    print(
        "\nFollow-up query to inspect results:\n"
        "  SELECT entity_name, region,\n"
        "         overall_score AS v1, signal_strength AS v1_tier,\n"
        "         v2_overall_score AS v2, v2_tier\n"
        "  FROM opportunity_signals\n"
        "  ORDER BY v2_overall_score DESC NULLS LAST\n"
        "  LIMIT 20;\n"
    )


if __name__ == "__main__":
    main()
