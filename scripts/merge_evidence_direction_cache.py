"""
Merge evidence_direction values from cache.json into evidence_counts.csv
"""
import json
import pandas as pd
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "evidence_counts.csv"
CACHE_PATH = ROOT / "data" / "evidence_direction_cache.json"
OUTPUT_PATH = ROOT / "data" / "evidence_counts.csv"

def main():
    print(f"📂 Reading CSV from: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"   Loaded {len(df)} rows")
    
    print(f"\n📂 Reading cache from: {CACHE_PATH}")
    with open(CACHE_PATH, 'r') as f:
        cache = json.load(f)
    print(f"   Loaded {len(cache)} cached evidence directions")
    
    # Create lookup key: condition|||therapy
    df['_lookup_key'] = df['condition'].astype(str) + '|||' + df['therapy'].astype(str)
    
    # Count before update
    before_counts = df['evidence_direction'].value_counts().to_dict()
    print(f"\n📊 Evidence direction counts BEFORE merge:")
    for direction, count in before_counts.items():
        print(f"   {direction}: {count}")
    
    # Update evidence_direction from cache
    updated_count = 0
    for idx, row in df.iterrows():
        lookup_key = row['_lookup_key']
        if lookup_key in cache:
            old_value = row['evidence_direction']
            new_value = cache[lookup_key]
            if old_value != new_value:
                df.at[idx, 'evidence_direction'] = new_value
                updated_count += 1
    
    print(f"\n✏️  Updated {updated_count} rows with cached values")
    
    # Count after update
    after_counts = df['evidence_direction'].value_counts().to_dict()
    print(f"\n📊 Evidence direction counts AFTER merge:")
    for direction, count in after_counts.items():
        print(f"   {direction}: {count}")
    
    # Remove temporary lookup column
    df = df.drop(columns=['_lookup_key'])
    
    # Save updated CSV
    print(f"\n💾 Saving updated CSV to: {OUTPUT_PATH}")
    df.to_csv(OUTPUT_PATH, index=False)
    print("✅ Done! Evidence directions have been updated in the CSV file.")
    
    # Show examples of what changed
    if updated_count > 0:
        print("\n📋 Example changes:")
        for key, direction in list(cache.items())[:5]:
            condition, therapy = key.split('|||')
            print(f"   {condition} + {therapy} = {direction}")

if __name__ == "__main__":
    main()

