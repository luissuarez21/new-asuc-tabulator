"""
Proposition Voting

Handles all four proposition types in the 2026 ASUC election, each with
distinct turnout thresholds and passage thresholds per the Tabulator Instructions.

Proposition Types:
  26A – Constitutional Amendment:  no turnout threshold, 60% passage threshold
  26B – Student Fee (All):         turnout threshold 8,760 yes+no, bare majority
  26C – Student Fee (Grad):        turnout threshold 2,513 yes+no, bare majority
  26D – Advisory:                  no turnout threshold, bare majority

"Bare majority" = yes strictly greater than 50% of (yes + no).
Turnout threshold = yes + no votes only (abstains excluded).
"""

from typing import Dict, Optional

# Per-proposition configuration keyed by the auto-detected prop_id.
# turnout_threshold: required yes+no votes (None = no threshold).
# passage_threshold: fraction of yes/(yes+no) required (strict >).
PROPOSITION_CONFIGS: Dict[str, Dict] = {
    "Proposition 26A": {
        "display_name": "Proposition 26A: The STRONG Act (Constitutional Amendment)",
        "turnout_threshold": None,
        "passage_threshold": 0.60,
    },
    "Proposition 26B": {
        "display_name": "Proposition 26B: Save Free Student Press Initiative (Student Fee - All Students)",
        "turnout_threshold": 8760,
        "passage_threshold": 0.50,
    },
    "Proposition 26C": {
        "display_name": "Proposition 26C: The GA Fee 2.0 (Student Fee - Graduate Students)",
        "turnout_threshold": 2513,
        "passage_threshold": 0.50,
    },
    "Proposition 26D": {
        "display_name": "Proposition 26D: Divestment (Advisory Proposition - All Students)",
        "turnout_threshold": None,
        "passage_threshold": 0.50,
    },
}


def run_proposition(votes: Dict[str, int], prop_id: str, prop_name: str) -> Dict:
    """
    Calculate proposition result using the rules for this specific proposition.

    Args:
        votes:     {"yes": count, "no": count, "abstain": count}
        prop_id:   Canonical key like "Proposition 26A" used to look up rules.
        prop_name: Full column name from CSV (used as fallback display label).

    Returns:
        Dict with complete results including passage/failure reason.
    """
    config = PROPOSITION_CONFIGS.get(prop_id)

    # Fall back to generic bare-majority rule for unrecognized propositions.
    if config is None:
        config = {
            "display_name": prop_name,
            "turnout_threshold": None,
            "passage_threshold": 0.50,
        }

    yes_votes = votes["yes"]
    no_votes = votes["no"]
    abstain_votes = votes["abstain"]

    total_turnout = yes_votes + no_votes + abstain_votes
    deciding_votes = yes_votes + no_votes  # abstains excluded from passage calc

    yes_percentage = (yes_votes / deciding_votes * 100) if deciding_votes > 0 else 0.0

    turnout_threshold: Optional[int] = config["turnout_threshold"]
    passage_threshold: float = config["passage_threshold"]

    # --- Turnout check (only applies to student-fee propositions) ---
    turnout_met: Optional[bool] = None  # None means "not applicable"
    if turnout_threshold is not None:
        turnout_met = deciding_votes >= turnout_threshold

    # --- Passage check ---
    # For bare majority (0.50): yes must be strictly greater than no.
    # For 60% threshold: yes/(yes+no) must be strictly greater than 60%.
    passage_met = yes_percentage > (passage_threshold * 100)

    # --- Determine final result ---
    if turnout_met is False:
        result = "NO PASSAGE - INSUFFICIENT TURNOUT"
    elif passage_met:
        result = "PASSAGE"
    else:
        result = "NO PASSAGE"

    return {
        "proposition": config["display_name"],
        "prop_id": prop_id,
        "yes_votes": yes_votes,
        "no_votes": no_votes,
        "abstain_votes": abstain_votes,
        "total_turnout": total_turnout,
        "deciding_votes": deciding_votes,
        "yes_percentage": yes_percentage,
        "passage_threshold_pct": passage_threshold * 100,
        "turnout_threshold": turnout_threshold,
        "turnout_met": turnout_met,
        "passage_met": passage_met,
        "result": result,
    }


def format_proposition_result(result: Dict) -> str:
    """Format proposition result for console output."""
    prop = result["proposition"]
    yes_v = result["yes_votes"]
    no_v = result["no_votes"]
    abstain_v = result["abstain_votes"]
    total = result["total_turnout"]
    deciding = result["deciding_votes"]
    yes_pct = result["yes_percentage"]
    pass_thresh = result["passage_threshold_pct"]
    turnout_thresh = result["turnout_threshold"]
    turnout_met = result["turnout_met"]
    outcome = result["result"]

    lines = []
    lines.append(f"\n{'='*65}")
    lines.append(f"{prop}")
    lines.append(f"{'='*65}")
    lines.append(f"Result: {outcome}")
    lines.append("")
    lines.append("Vote Breakdown:")
    lines.append(f"  Yes:     {yes_v:>7}")
    lines.append(f"  No:      {no_v:>7}")
    lines.append(f"  Abstain: {abstain_v:>7}")
    lines.append("")
    lines.append(f"Total Turnout:  {total:>7}")
    lines.append(f"Deciding Votes: {deciding:>7}  (Yes + No, abstains excluded)")
    lines.append(f"Yes Share:      {yes_pct:>6.1f}%  (of deciding votes)")
    lines.append("")

    # Turnout threshold line
    if turnout_thresh is not None:
        status = "MET" if turnout_met else "NOT MET"
        lines.append(f"Turnout Threshold: {turnout_thresh:,} yes+no votes required – {status}")
    else:
        lines.append("Turnout Threshold: N/A (no turnout threshold for this proposition)")

    # Passage threshold line
    lines.append(f"Passage Threshold: >{pass_thresh:.0f}% of deciding votes required")

    return "\n".join(lines)
