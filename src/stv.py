"""
Single Transferable Vote (STV) - Senate Race

Implements STV per ASUCBL 4105 Section 4 for multi-winner race:
- Senate: 20 seats from ~37 candidates

Algorithm:
1. Count first preferences (each ballot starts with value 1.0)
2. Quota = floor((N/(S+1)) + 1) where N = valid first prefs, S = seats (20)
3. TWO TYPES OF ROUNDS:
   a) ELECTION ROUND: If candidate(s) reach quota:
      - ELECT them
      - Transfer SURPLUS at reduced value: V * (C-Q)/C
        where V = vote value when elected, C = candidate's total, Q = quota
   b) ELIMINATION ROUND: If no one reaches quota:
      - Eliminate lowest vote-total candidate(s)
      - Transfer votes at CURRENT value (may be fractional)
4. Repeat until 20 seats filled or only <=20 candidates remain

Critical Rules:
- Votes have FRACTIONAL values (use Decimal for precision)
- Transfer to NEXT non-eliminated, non-elected preference
- If all preferences exhausted -> ballot drops out
- Track vote values through all rounds

Edge Cases:
- Multiple candidates elected same round -> transfer all surpluses
- Tied for last elimination -> eliminate all tied candidates
- End condition: remaining candidates <= unfilled seats -> elect them all
"""

from decimal import Decimal, ROUND_FLOOR
from typing import Dict, List, Set, Optional
from copy import deepcopy


class Ballot:
    """
    Represents a single ballot with fractional vote value.

    Attributes:
        preferences: Ordered list of candidate dicts
        current_value: Current vote value (starts at 1.0, may be reduced by surplus transfers)
        current_position: Index in preferences list
        ballot_id: For debugging (optional)
    """

    def __init__(self, preferences: List[Dict], ballot_id: int = 0):
        self.preferences = preferences
        self.current_value = Decimal('1.0')
        self.current_position = 0
        self.ballot_id = ballot_id

    def get_current_preference(self, eliminated: Set[str], elected: Set[str]) -> Optional[str]:
        """
        Get next valid preference, skipping eliminated/elected candidates.

        Args:
            eliminated: Set of eliminated candidate names (lowercase)
            elected: Set of elected candidate names (lowercase)

        Returns:
            Candidate name, or None if ballot exhausted
        """
        while self.current_position < len(self.preferences):
            candidate = self.preferences[self.current_position]
            candidate_key = candidate['name'].lower()

            if candidate_key not in eliminated and candidate_key not in elected:
                return candidate['name']  # Return original case

            self.current_position += 1

        return None  # Ballot exhausted

    def advance_to_next_preference(self):
        """Move to next preference in list."""
        self.current_position += 1

    def reduce_value(self, transfer_factor: Decimal):
        """
        Reduce ballot value by transfer factor.

        Args:
            transfer_factor: Multiplier (e.g., (C-Q)/C for surplus transfer)
        """
        self.current_value *= transfer_factor

    def __repr__(self):
        return f"Ballot(id={self.ballot_id}, value={self.current_value}, pos={self.current_position})"


def calculate_stv_quota(valid_ballots: int, seats: int) -> int:
    """
    Calculate STV quota per ASUCBL 4105 Section 4.

    Args:
        valid_ballots: Number of valid first-preference votes
        seats: Number of seats to fill (20 for Senate)

    Returns:
        Quota = floor((N/(S+1)) + 1)

    Example:
        N=11000, S=20 -> floor((11000/21) + 1) = floor(524.76 + 1) = floor(525.76) = 525
    """
    quota_decimal = Decimal(valid_ballots) / Decimal(seats + 1) + Decimal('1')
    return int(quota_decimal.to_integral_value(rounding=ROUND_FLOOR))


def count_current_votes(ballots: List[Ballot], eliminated: Set[str], elected: Set[str]) -> Dict[str, Decimal]:
    """
    Sum up fractional vote values for each candidate.

    Args:
        ballots: List of Ballot objects
        eliminated: Set of eliminated candidate names (lowercase)
        elected: Set of elected candidate names (lowercase)

    Returns:
        Dict mapping candidate name -> total vote value (Decimal)
    """
    vote_totals = {}

    for ballot in ballots:
        current_pref = ballot.get_current_preference(eliminated, elected)

        if current_pref:
            if current_pref not in vote_totals:
                vote_totals[current_pref] = Decimal('0')
            vote_totals[current_pref] += ballot.current_value

    return vote_totals


def find_elected_candidates(standings: Dict[str, Decimal], quota: int, already_elected: Set[str]) -> List[str]:
    """
    Find candidates who reached quota this round.

    Args:
        standings: Current vote totals
        quota: Winning threshold
        already_elected: Set of already-elected candidate names (lowercase)

    Returns:
        List of newly-elected candidate names
    """
    newly_elected = []

    for candidate, votes in standings.items():
        if candidate.lower() not in already_elected and votes >= quota:
            newly_elected.append(candidate)

    return newly_elected


def find_lowest_candidates(standings: Dict[str, Decimal], eliminated: Set[str], elected: Set[str]) -> List[str]:
    """
    Find candidate(s) with lowest vote total (handle ties).

    Args:
        standings: Current vote totals
        eliminated: Already-eliminated candidates (lowercase)
        elected: Already-elected candidates (lowercase)

    Returns:
        List of candidate names tied for lowest

    Note:
        Per ASUCBL 4105 Section 4.3.7, if multiple tie for last, eliminate all
        (unless special tie-breaking procedures apply).
    """
    # Filter out already-eliminated/elected candidates
    active_standings = {
        candidate: votes
        for candidate, votes in standings.items()
        if candidate.lower() not in eliminated and candidate.lower() not in elected
    }

    if not active_standings:
        return []

    min_votes = min(active_standings.values())
    return [candidate for candidate, votes in active_standings.items() if votes == min_votes]


def transfer_surplus(ballots: List[Ballot], elected_candidate: str, surplus: Decimal,
                     candidate_total: Decimal, eliminated: Set[str], elected: Set[str]):
    """
    Transfer surplus from elected candidate.

    Args:
        ballots: List of Ballot objects
        elected_candidate: Name of newly-elected candidate
        surplus: candidate_total - quota
        candidate_total: Total votes candidate received when elected
        eliminated: Set of eliminated candidates (lowercase)
        elected: Set of elected candidates (lowercase) - should include elected_candidate

    Behavior:
        For each ballot currently supporting elected_candidate:
        - Reduce vote value: new_value = old_value * (surplus / candidate_total)
        - Advance to next preference
        - Next round will count it for that preference

    Per ASUCBL 4105 Section 4.2.4:
        New vote value = V * (C - Q) / C
        where V = current value, C = candidate's total, Q = quota
    """
    if candidate_total == 0:
        return  # Avoid division by zero

    transfer_factor = surplus / candidate_total

    for ballot in ballots:
        current_pref = ballot.get_current_preference(eliminated, elected - {elected_candidate.lower()})

        if current_pref == elected_candidate:
            # Reduce value and advance
            ballot.reduce_value(transfer_factor)
            ballot.advance_to_next_preference()


def transfer_eliminated_votes(ballots: List[Ballot], eliminated_candidates: List[str],
                                eliminated: Set[str], elected: Set[str]):
    """
    Transfer votes from eliminated candidates at current value.

    Args:
        ballots: List of Ballot objects
        eliminated_candidates: List of newly-eliminated candidate names
        eliminated: Set of all eliminated candidates (lowercase) - should include eliminated_candidates
        elected: Set of elected candidates (lowercase)

    Behavior:
        For each ballot currently supporting an eliminated candidate:
        - Keep vote value UNCHANGED (unlike surplus transfer)
        - Advance to next non-eliminated, non-elected preference
        - If no valid preference, ballot exhausts
    """
    for ballot in ballots:
        current_pref = ballot.get_current_preference(eliminated - set(c.lower() for c in eliminated_candidates), elected)

        if current_pref in eliminated_candidates:
            # Advance to next preference (value stays same)
            ballot.advance_to_next_preference()


def run_stv(ballots_raw: List[List[Dict]], seats: int = 20, race_name: str = "Senate") -> Dict:
    """
    Run Single Transferable Vote election.

    Args:
        ballots_raw: List of ranked ballots (from csv_parser.extract_race_ballots)
        seats: Number of seats to fill (default 20 for Senate)
        race_name: Name of race for display

    Returns:
        Dict with complete results:
        {
            "race": str,
            "seats": int,
            "elected": [list of elected candidate dicts in election order],
            "rounds": [
                {
                    "round_num": int,
                    "round_type": "election" or "elimination",
                    "standings": {candidate: vote_total},
                    "quota": int,
                    "total_active_ballots": Decimal,
                    "exhausted_count": int,
                    "elected_this_round": [candidates] or [],
                    "eliminated_this_round": [candidates] or [],
                    "vote_transfers": {candidate: (surplus or votes_transferred)}
                },
                ...
            ],
            "total_ballots": int,
            "final_exhausted": int
        }

    Per ASUCBL 4105 Section 4.
    """
    if not ballots_raw:
        return {
            "race": race_name,
            "seats": seats,
            "elected": [],
            "rounds": [],
            "total_ballots": 0,
            "final_exhausted": 0,
            "error": "No valid ballots"
        }

    # Convert to Ballot objects
    ballots = [Ballot(ballot, idx) for idx, ballot in enumerate(ballots_raw)]
    total_ballots = len(ballots)

    eliminated = set()
    elected_set = set()  # lowercase names
    elected_list = []  # full candidate info in election order
    election_rounds = {}  # Track which round each candidate was elected in
    final_vote_totals = {}  # Track final vote total for each elected candidate
    rounds = []
    round_num = 0

    # Calculate quota (based on initial ballots)
    quota = calculate_stv_quota(total_ballots, seats)

    print(f"\n{'='*60}")
    print(f"STV: {race_name}")
    print(f"{'='*60}")
    print(f"Total ballots: {total_ballots}")
    print(f"Seats to fill: {seats}")
    print(f"Quota: {quota}")
    print()

    while len(elected_list) < seats:
        round_num += 1

        # Count current votes
        standings = count_current_votes(ballots, eliminated, elected_set)

        if not standings:
            print(f"[WARNING] All ballots exhausted in round {round_num}")
            break

        # Calculate active ballots (sum of all vote values)
        total_active_value = sum(standings.values())
        exhausted_count = total_ballots - sum(1 for b in ballots if b.get_current_preference(eliminated, elected_set))

        # Check if we should just elect remaining candidates
        active_candidates = [c for c in standings.keys() if c.lower() not in eliminated and c.lower() not in elected_set]
        remaining_seats = seats - len(elected_list)

        if len(active_candidates) <= remaining_seats:
            print(f"Round {round_num}: Electing all remaining {len(active_candidates)} candidates")
            for candidate in active_candidates:
                if candidate.lower() not in elected_set:  # Double-check not already elected
                    elected_set.add(candidate.lower())
                    # Find full candidate info
                    cand_info = None
                    for ballot_raw in ballots_raw:
                        for cand_dict in ballot_raw:
                            if cand_dict['name'] == candidate:
                                cand_info = cand_dict
                                break
                        if cand_info:
                            break
                    if cand_info:
                        elected_list.append(cand_info)
                        # Store election round and final vote total
                        election_rounds[candidate] = round_num
                        final_vote_totals[candidate] = float(standings.get(candidate, Decimal('0')))
                        print(f"  >>> {candidate} ELECTED (remaining candidate)")

            rounds.append({
                "round_num": round_num,
                "round_type": "final_election",
                "standings": {k: float(v) for k, v in standings.items()},
                "quota": quota,
                "total_active_ballots": float(total_active_value),
                "exhausted_count": exhausted_count,
                "elected_this_round": active_candidates,
                "eliminated_this_round": [],
                "vote_transfers": {}
            })
            break

        # Check for newly-elected candidates
        newly_elected = find_elected_candidates(standings, quota, elected_set)

        if newly_elected:
            # ELECTION ROUND
            print(f"Round {round_num}: ELECTION ROUND")
            print(f"  Active vote value: {float(total_active_value):.2f}, Quota: {quota}")
            print(f"  Top standings:")
            for candidate, votes in sorted(standings.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"    {candidate}: {float(votes):.2f}")

            vote_transfers = {}

            for candidate in newly_elected:
                elected_set.add(candidate.lower())

                # Find full candidate info
                cand_info = None
                for ballot_raw in ballots_raw:
                    for cand_dict in ballot_raw:
                        if cand_dict['name'] == candidate:
                            cand_info = cand_dict
                            break
                    if cand_info:
                        break

                elected_list.append(cand_info)

                # Calculate and transfer surplus
                candidate_total = standings[candidate]
                surplus = candidate_total - quota

                # Store election round and final vote total
                election_rounds[candidate] = round_num
                final_vote_totals[candidate] = float(candidate_total)

                print(f"  >>> {candidate} ELECTED (votes: {float(candidate_total):.2f}, surplus: {float(surplus):.2f})")

                if surplus > 0:
                    transfer_surplus(ballots, candidate, surplus, candidate_total, eliminated, elected_set)
                    vote_transfers[candidate] = float(surplus)

            rounds.append({
                "round_num": round_num,
                "round_type": "election",
                "standings": {k: float(v) for k, v in standings.items()},
                "quota": quota,
                "total_active_ballots": float(total_active_value),
                "exhausted_count": exhausted_count,
                "elected_this_round": newly_elected,
                "eliminated_this_round": [],
                "vote_transfers": vote_transfers
            })

        else:
            # ELIMINATION ROUND
            lowest_candidates = find_lowest_candidates(standings, eliminated, elected_set)

            if not lowest_candidates:
                print(f"[WARNING] No candidates to eliminate in round {round_num}")
                break

            print(f"Round {round_num}: ELIMINATION ROUND")
            print(f"  Active vote value: {float(total_active_value):.2f}")
            print(f"  Bottom standings:")
            for candidate, votes in sorted(standings.items(), key=lambda x: x[1])[:5]:
                print(f"    {candidate}: {float(votes):.2f}")

            votes_eliminated = sum(standings.get(c, Decimal('0')) for c in lowest_candidates)
            print(f"  Eliminating: {', '.join(lowest_candidates)} ({float(votes_eliminated):.2f} votes)")

            for candidate in lowest_candidates:
                eliminated.add(candidate.lower())

            transfer_eliminated_votes(ballots, lowest_candidates, eliminated, elected_set)

            rounds.append({
                "round_num": round_num,
                "round_type": "elimination",
                "standings": {k: float(v) for k, v in standings.items()},
                "quota": quota,
                "total_active_ballots": float(total_active_value),
                "exhausted_count": exhausted_count,
                "elected_this_round": [],
                "eliminated_this_round": lowest_candidates,
                "vote_transfers": {c: float(standings.get(c, Decimal('0'))) for c in lowest_candidates}
            })

    final_exhausted = sum(1 for b in ballots if b.get_current_preference(eliminated, elected_set) is None)

    # Sort elected senators by:
    # 1. Election round (ascending - earlier rounds first)
    # 2. Within same round, by final vote total (descending - higher votes first)
    elected_list_sorted = sorted(
        elected_list,
        key=lambda x: (
            election_rounds.get(x['name'], 999),
            -final_vote_totals.get(x['name'], 0)  # Negative for descending order
        )
    )

    print(f"\n{'='*60}")
    print(f"ELECTION COMPLETE - {len(elected_list_sorted)} seats filled")
    print(f"{'='*60}\n")

    return {
        "race": race_name,
        "seats": seats,
        "elected": elected_list_sorted,
        "rounds": rounds,
        "total_ballots": total_ballots,
        "final_exhausted": final_exhausted
    }


