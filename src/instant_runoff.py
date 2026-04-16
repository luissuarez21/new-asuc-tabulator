"""
Instant Runoff Voting (IRV) - Executive Races

Implements IRV per ASUCBL 4105 Section 3 for single-winner races:
- President
- Executive Vice President
- External Affairs Vice President
- Academic Affairs Vice President
- Student Advocate

Algorithm:
1. Count first preferences
2. Quota = (N+1)/2 where N = valid first-preference votes
3. If candidate reaches quota -> ELECTED
4. If no one reaches quota:
   - Eliminate candidate(s) with fewest votes
   - Transfer votes at full value (1.0) to next preference
   - Skip eliminated candidates in preferences
   - Exhaust ballot if no remaining valid preferences
5. Repeat until winner found

Edge Cases:
- Ties for elimination: eliminate all tied-lowest candidates
- Ballot exhaustion: ballot has no more valid preferences
- Only 1 candidate remains: they win by default
- Skipped preferences: already handled by csv_parser (compacted)
"""

from typing import Dict, List, Set, Optional
from copy import deepcopy


def count_first_preferences(ballots: List[List[Dict]], eliminated: Set[str], elected: Set[str]) -> Dict[str, int]:
    """
    Count current first preferences for each candidate.

    Args:
        ballots: List of ranked ballots (each ballot is list of candidate dicts)
        eliminated: Set of eliminated candidate names (lowercase)
        elected: Set of elected candidate names (lowercase) - for IRV this is empty until end

    Returns:
        Dict mapping candidate name -> vote count

    Behavior:
        - Skip eliminated/elected candidates
        - Move to next preference if current preference is eliminated
        - Exhaust ballot if no valid preferences remain
    """
    vote_counts = {}

    for ballot in ballots:
        # Find first non-eliminated, non-elected candidate
        current_pref = get_next_preference(ballot, eliminated, elected)

        if current_pref:
            vote_counts[current_pref] = vote_counts.get(current_pref, 0) + 1

    return vote_counts


def get_next_preference(ballot: List[Dict], eliminated: Set[str], elected: Set[str]) -> Optional[str]:
    """
    Get next valid preference from ballot, skipping eliminated/elected candidates.

    Args:
        ballot: Ordered list of candidate preferences
        eliminated: Set of eliminated candidate names (lowercase)
        elected: Set of elected candidate names (lowercase)

    Returns:
        Candidate name, or None if ballot exhausted
    """
    for candidate in ballot:
        candidate_key = candidate['name'].lower()
        if candidate_key not in eliminated and candidate_key not in elected:
            return candidate['name']  # Return original case

    return None  # Ballot exhausted


def calculate_quota(valid_ballots: int) -> float:
    """
    Calculate IRV quota per ASUCBL 4105 Section 3.

    Args:
        valid_ballots: Number of valid first-preference votes

    Returns:
        Quota = (N + 1) / 2

    Note:
        This is a simple majority. In IRV, only one candidate needs to reach this
        to win (unlike STV where multiple candidates can be elected).
    """
    return (valid_ballots + 1) / 2


def find_lowest_candidates(standings: Dict[str, int]) -> List[str]:
    """
    Find candidate(s) with fewest votes (handle ties).

    Args:
        standings: Dict mapping candidate name -> vote count

    Returns:
        List of candidate names tied for lowest vote count

    Note:
        Per ASUCBL 4105 Section 3.3.9, if multiple candidates tie for last,
        eliminate all of them (unless special tie-breaking procedures apply).
    """
    if not standings:
        return []

    min_votes = min(standings.values())
    return [candidate for candidate, votes in standings.items() if votes == min_votes]


def check_for_winner(standings: Dict[str, int], quota: float) -> Optional[str]:
    """
    Check if any candidate has reached quota.

    Args:
        standings: Current vote counts
        quota: Winning threshold

    Returns:
        Winning candidate name, or None if no winner yet
    """
    for candidate, votes in standings.items():
        if votes >= quota:
            return candidate
    return None


def run_instant_runoff(ballots: List[List[Dict]], race_name: str) -> Dict:
    """
    Run Instant Runoff Voting election.

    Args:
        ballots: List of ranked ballots (from csv_parser.extract_race_ballots)
        race_name: Name of race for display

    Returns:
        Dict with complete results:
        {
            "race": str,
            "winner": Dict (candidate info),
            "rounds": [
                {
                    "round_num": int,
                    "standings": {candidate: vote_count},
                    "quota": float,
                    "total_active_ballots": int,  # Non-exhausted
                    "exhausted_this_round": int,
                    "eliminated": [candidates] or None,
                    "winner": candidate or None
                },
                ...
            ],
            "total_ballots": int,
            "final_exhausted": int
        }

    Per ASUCBL 4105 Section 3.
    """
    if not ballots:
        return {
            "race": race_name,
            "winner": None,
            "rounds": [],
            "total_ballots": 0,
            "final_exhausted": 0,
            "error": "No valid ballots for this race"
        }

    total_ballots = len(ballots)
    eliminated = set()
    elected = set()
    rounds = []
    round_num = 0

    print(f"\n{'='*60}")
    print(f"IRV: {race_name}")
    print(f"{'='*60}")
    print(f"Total ballots: {total_ballots}\n")

    while True:
        round_num += 1

        # Count current first preferences
        standings = count_first_preferences(ballots, eliminated, elected)

        if not standings:
            # All ballots exhausted - shouldn't happen in practice
            print(f"[WARNING] All ballots exhausted in round {round_num}")
            break

        # Calculate quota based on CURRENT active ballots
        active_ballots = sum(standings.values())
        quota = calculate_quota(active_ballots)
        exhausted_count = total_ballots - active_ballots

        # Display round info
        print(f"Round {round_num}:")
        print(f"  Active ballots: {active_ballots}, Quota: {quota:.2f}")
        print(f"  Standings:")
        for candidate, votes in sorted(standings.items(), key=lambda x: x[1], reverse=True):
            pct = (votes / active_ballots * 100) if active_ballots > 0 else 0
            print(f"    {candidate}: {votes} ({pct:.1f}%)")

        # Check for winner
        winner_name = check_for_winner(standings, quota)

        if winner_name:
            print(f"  >>> {winner_name} reaches quota - ELECTED!")

            # Find winner's full info from first ballot that ranks them
            winner_info = None
            for ballot in ballots:
                for candidate in ballot:
                    if candidate['name'] == winner_name:
                        winner_info = candidate
                        break
                if winner_info:
                    break

            rounds.append({
                "round_num": round_num,
                "standings": standings.copy(),
                "quota": quota,
                "total_active_ballots": active_ballots,
                "exhausted_this_round": exhausted_count,
                "eliminated": None,
                "winner": winner_name
            })

            return {
                "race": race_name,
                "winner": winner_info,
                "rounds": rounds,
                "total_ballots": total_ballots,
                "final_exhausted": exhausted_count
            }

        # No winner - eliminate lowest candidate(s)
        lowest_candidates = find_lowest_candidates(standings)

        # Edge case: only 1 candidate left (everyone else eliminated)
        if len(standings) == 1:
            remaining_candidate = list(standings.keys())[0]
            print(f"  >>> Only {remaining_candidate} remains - ELECTED by default!")

            # Find winner's full info
            winner_info = None
            for ballot in ballots:
                for candidate in ballot:
                    if candidate['name'] == remaining_candidate:
                        winner_info = candidate
                        break
                if winner_info:
                    break

            rounds.append({
                "round_num": round_num,
                "standings": standings.copy(),
                "quota": quota,
                "total_active_ballots": active_ballots,
                "exhausted_this_round": exhausted_count,
                "eliminated": None,
                "winner": remaining_candidate
            })

            return {
                "race": race_name,
                "winner": winner_info,
                "rounds": rounds,
                "total_ballots": total_ballots,
                "final_exhausted": exhausted_count
            }

        # Eliminate lowest candidate(s)
        for candidate in lowest_candidates:
            eliminated.add(candidate.lower())

        votes_eliminated = sum(standings[c] for c in lowest_candidates)
        print(f"  Eliminating: {', '.join(lowest_candidates)} ({votes_eliminated} votes)")

        rounds.append({
            "round_num": round_num,
            "standings": standings.copy(),
            "quota": quota,
            "total_active_ballots": active_ballots,
            "exhausted_this_round": exhausted_count,
            "eliminated": lowest_candidates,
            "winner": None
        })

    # Should never reach here
    return {
        "race": race_name,
        "winner": None,
        "rounds": rounds,
        "total_ballots": total_ballots,
        "final_exhausted": total_ballots,
        "error": "Election did not converge"
    }


