"""
ASUC Elections Tabulator - Flexible Main Orchestrator

Works with any year's CSV format by auto-detecting races and propositions.
"""

import sys
import json
from datetime import datetime

# Import modules
import csv_parser as csv_parser
import propositions
import instant_runoff
import stv


def main(csv_filepath: str):
    """
    Main orchestrator with auto-detection for any year's format.
    """
    print("\n" + "="*70)
    print(" ASUC ELECTIONS TABULATOR (Flexible)")
    print("="*70 + "\n")

    # ========================================================================
    # STEP 1: Load CSV and Auto-Detect Races
    # ========================================================================
    print("[STEP 1] Loading CSV and auto-detecting races...")
    df = csv_parser.load_csv(csv_filepath)

    # Auto-detect races
    race_configs = csv_parser.auto_detect_races(df)
    print(f"\n[OK] Auto-detected {len(race_configs)} races")
    for race_name in race_configs.keys():
        print(f"  - {race_name}")

    # Auto-detect propositions
    prop_configs = csv_parser.auto_detect_propositions(df)
    print(f"\n[OK] Auto-detected {len(prop_configs)} propositions")
    for prop_id in prop_configs.keys():
        print(f"  - {prop_id}")

    # ========================================================================
    # STEP 2: Run Executive Races (IRV)
    # ========================================================================
    print("\n" + "="*70)
    print("[STEP 2] EXECUTIVE RACES (Instant Runoff Voting)")
    print("="*70)

    executive_results = {}
    executive_races = [name for name, config in race_configs.items() if config['type'] == 'irv']

    for race_name in executive_races:
        race_config = race_configs[race_name]
        ballots = csv_parser.extract_race_ballots(df, race_config)

        if ballots:
            result = instant_runoff.run_instant_runoff(ballots, race_name)
            executive_results[race_name] = result

    # ========================================================================
    # STEP 3: Run Senate Race (STV)
    # ========================================================================
    print("\n" + "="*70)
    print("[STEP 3] SENATE RACE (Single Transferable Vote)")
    print("="*70)

    senate_result = None
    if "Senate" in race_configs:
        senate_config = race_configs["Senate"]
        senate_ballots = csv_parser.extract_race_ballots(df, senate_config)
        if senate_ballots:
            senate_result = stv.run_stv(senate_ballots, seats=20, race_name="Senate")
    else:
        print("\n[WARNING] No Senate race detected in this election")

    # ========================================================================
    # STEP 4: Run Propositions (Simple Majority)
    # ========================================================================
    print("\n" + "="*70)
    print("[STEP 4] PROPOSITIONS (Simple Majority)")
    print("="*70 + "\n")

    proposition_results = {}

    for prop_id, prop_config in prop_configs.items():
        votes = csv_parser.get_proposition_votes(df, prop_config, prop_id)
        result = propositions.run_proposition(votes, prop_id, prop_config['name'])
        proposition_results[prop_id] = result
        print(propositions.format_proposition_result(result))

    # ========================================================================
    # STEP 5: Generate results.json
    # ========================================================================
    print("\n" + "="*70)
    print("[STEP 5] Generating results.json")
    print("="*70 + "\n")

    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_ballots": len(df),
        "executive_races": executive_results,
        "senate": senate_result if senate_result else {},
        "propositions": proposition_results
    }

    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "..", "output", "results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"[OK] Results saved to: {output_path}")

    # ========================================================================
    # STEP 6: Print Summary
    # ========================================================================
    print("\n" + "="*70)
    print(" ELECTION RESULTS SUMMARY")
    print("="*70 + "\n")

    print(f"Total Ballots Processed: {len(df)}\n")

    # Executive Winners
    if executive_results:
        print("--- EXECUTIVE OFFICERS ---")
        for race_name, result in executive_results.items():
            if result and result.get('winner'):
                winner = result['winner']
                name = winner['name']
                party = winner.get('party', 'N/A')
                rounds = len(result['rounds'])
                print(f"{race_name}:")
                print(f"  Winner: {name} ({party})")
                print(f"  Rounds: {rounds}\n")

    # Senate Winners
    if senate_result and senate_result.get('elected'):
        print("--- SENATE (20 Seats) ---")
        print(f"Rounds: {len(senate_result['rounds'])}")
        print(f"Elected Senators:")
        for i, senator in enumerate(senate_result['elected'], 1):
            name = senator['name']
            party = senator.get('party', 'N/A')
            print(f"  {i:2d}. {name} ({party})")

    # Propositions
    if proposition_results:
        print("\n--- PROPOSITIONS ---")
        for prop_id, result in proposition_results.items():
            outcome = result['result']
            yes_pct = result['yes_percentage']
            turnout_thresh = result.get('turnout_threshold')
            deciding = result['deciding_votes']
            turnout_note = ""
            if turnout_thresh is not None:
                turnout_note = f", turnout {deciding:,}/{turnout_thresh:,}"
            print(f"{prop_id}: {outcome} ({yes_pct:.1f}% yes{turnout_note})")

    print("\n" + "="*70)
    print(" TABULATION COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = r"data\Test 2026 ballot 3.csv"

    main(csv_file)
