"""
The purpose of this parser is to Auto-detect races and propositions from any year's CSV format.
It handles variations in column naming across different elections years.
"""

import pandas as pd
import re
from typing import Dict, List, Optional, Tuple

def load_csv(filepath: str) -> pd.DataFrame:
    """Load ASUC election CSV file."""

    try:
        df = pd.read_csv(filepath, skiprows = 2, low_memory=False)
        if 'SubmissionId' not in df.columns: #no Submission ID column in CSV loaded.
            raise ValueError("CSV missing required 'SubmissionId'")
        
        print(f"[OK] Loaded {len(df)} ballots from {filepath} and found {len(df.columns)} columns")
        return df
    
    except Exception as e:
        raise ValueError(f"Error loading CSV: {str(e)}") #displays any error
    

def parse_candidate_cell(cell_value: any) -> Optional[Dict[str, any]]:
    """Parse candidate string into structured data."""
    if pd.isna(cell_value) or not isinstance(cell_value, str) or cell_value.strip() == "":
        return None
    
    cell_value = cell_value.strip() #if cell_value surrounded by spaces (i.e. " xyxy ") will remove -> "xyxy"
    
    if cell_value.lower() == "abstain": #abstain = None
        return None
    
    parts = [p.strip() for p in cell_value.split('|')] 
        # candidate | party | description -> [candidate, party, description]
        # None of the above -> [None of the Above]

    return {
        "name": parts[0],
        "party": parts[1] if len(parts) > 1 else "",
        "description": parts[2] if len(parts) > 2 else "",
    }

def coalesce_row_values(row: pd.Series, column_variants: List[str]) -> any:
    """Get first non-empty value from duplicate columns."""
    for col in column_variants:
        if col in row.index:
            val = row[col]
            if pd.notna(val) and val != '':
                return val
    return pd.NA

def auto_detect_races(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Auto-detect all races in the CSV by analyzing column patterns.
    
    Returns dict of race configs:
    {
        "President": {"name": "President", "columns": [...], "type": 'irv"},
        "Senate": {"name": "Senate", "columns": [...], "type": "stv", "seats": 20},
        ...
    }
    """

    races = {}

    # Pattern 1: Look for numbered ranking columns
    # Examples: "President - 1",  "President Candidates - 1", "Senate - 1"
    # Group columns by their base name (everything before " - NUMBER")

    column_groups = {}
    for col in df.columns:
        # Match pattern: "Something - NUMBER" or "Something Candidates - NUMBER"
        match = re.match(r'^(.+?)\s*(?:Candidates)?\s*-\s*(\d+)$')
        if match:
            base_name = match.group(1).strip()
            rank_num = int(match.group(2))

            #Skip description/instruction columns
            if len(base_name) > 100 or 'rank' in base_name.lower():
                continue

            if base_name not in column_groups:
                column_groups[base_name] = []
            column_groups[base_name].append((rank_num, col))
    
    # Sort and create race configs
    for base_name, column_list in column_groups.items():
        # Sort by rank number
        columns_list.sort(key=lambda x: x[0])
        columns = [col for rank, col in columns_list]

        #Determine race type
        race_lower = base_name.lower()

        if 'senate' in race_lower or 'senator' in race_lower:
            races["Senate"] = {
                "name": "Senate",
                "columns": columns,
                "type": "stv",
                "seats": 20
            }
        elif 'president' in race_lower and 'vice' not in race_lower:
            races["President"] = {
                "name": "President",
                "columns": columns,
                "type": "irv"
            }
        elif 'executive vice president' in race_lower or 'evp' in race_lower:
            races["Executive Vice President"] = {
                "name": "Executive Vice President",
                "columns": columns,
                "type": "irv"
            }
        elif 'external' in race_lower and ('vice president' in race_lower or 'vp' in race_lower):
            races["External Affairs Vice President"] = {
                "name": "External Affairs Vice President",
                "columns": columns,
                "type": "irv"
            }
        elif 'academic' in race_lower and ('vice president' in race_lower or 'vp' in race_lower):
            races["Academic Affairs Vice President"] = {
                "name": "Academic Affairs Vice President",
                "columns": columns,
                "type": "irv"
            }
        elif 'advocate' in race_lower or 'sao' in race_lower:
            races["Student Advocate"] = {
                "name": "Student Advocate",
                "columns": columns,
                "type": "irv"
            }
        elif 'transfer' in race_lower or 'transfer student representative' in race_lower:
            races["Transfer Representative"] = {
                "name": "Transfer Representative",
                "columns": columns,
                "type": "irv"
            }
        # add more races here if needed
    return races

def auto_detect_propositions(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Auto-detect propositions in the CSV

    Looks for columns with patterns like:
    - "Proposition 25A: ..."
    - "Proposition 18B Student Fee: ..."
    - "Measure X: ..."

    Returns dict of proposition configs.
    """

    propositions = {}

    for col in df.columns:
        col_lower = col.lower()

        # check if it is a proposition column (short name, not description of proposition)
        if 'proposition' in col_lower and len(col) < 50:
            # Extract Proposition ID
            match = re.match(r'(proposition)\s+([0-9]+[a-z]?)', col, re.IGNORECASE)
            if match:
                prop_type = match.group(1).title()
                prop_num = match.group(2).upper()
                prop_id = f"{prop_type} {prop_num}"

                propositions[prop_id] = {
                    "name": col.strip(),
                    "column": col
                }

    return propositions

def extract_race_ballots(df: pd.DataFrame, race_config: Dict[str, any]) -> List[List[Dict]]:
    """ Extract ranked preferences for a specific race (same as before)."""
    ballots = []
    base_columns = race_config['columns']
    race_name = race_config['name']

    column_sets = []
    for base_col in base_columns:
        variants = [col for col in df.columns if col == base_col or col]
        if variants:
            column_sets.append(variants)
    
    if not column_sets:
        print(f" [WARNING] No columns found for {race_name}")
        return []
    
    for idx, row in df.iterrows():
        ballot = []
        seen_candidates = set()

        for column_variants in column_sets:
            cell_value = coalesce_row_values(row, column_variants)
            candidate = parse_candidate_cell(cell_value)

            if candidate is not None:
                candidate_key = candidate['name'].lower()
                if candidate_key in seen_candidates:
                    continue
                ballot.append(candidate)
                seen_candidates.add(candidate_key)

        if ballot:
            ballots.append(ballot)

    print(f"  [OK] {race_name}: {len(ballots)} valid ballots extracted")
    return ballots

def get_proposition_votes(df: pd.DataFrame, prop_config: Dict[str, str]) -> Dict[str, int]:
    """Count Yes/No/Abstain votes for a proposition (same as before)."""
    base_column = prop_config['column']
    column_variants = [col for col in df.columns if col == base_column or col.startswith(base_column + '.')]

    if not column_variants:
        print(f"  [WARNING] Proposition column '{base_column}' not found")
        return {"yes": 0, "no": 0, "abstain": 0}

    votes = {"yes": 0, "no": 0, "abstain": 0}

    for idx, row in df.iterrows():
        value = coalesce_row_values(row, column_variants)

        if pd.isna(value) or value == "":
            votes["abstain"] += 1
        else:
            value_lower = str(value).strip().lower()
            if value_lower == "yes":
                votes["yes"] += 1
            elif value_lower == "no":
                votes["no"] += 1
            elif value_lower == "abstain":
                votes["abstain"] += 1
            else:
                votes["abstain"] += 1

    return votes

    
    



    