#!/usr/bin/env python3
"""
Organize submissions into groups based on bins from Excel file.
"""

import pandas as pd
import shutil
from pathlib import Path

# Paths
EXCEL_FILE = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/assignment_7153640_export/final_group_marks_with_bins.xlsx"
SOURCE_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/assignment_7153640_export")
TARGET_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/Tournament_1/Group_Stage")

def main():
    print("📊 Reading Excel file...")
    # Read the Excel file
    df = pd.read_excel(EXCEL_FILE)
    
    print(f"✅ Found {len(df)} submissions")
    print(f"Columns: {list(df.columns)}")
    print()
    
    # Check if required columns exist
    if 'submission_key' not in df.columns or 'bin' not in df.columns:
        print("❌ Error: Excel file must have 'submission_key' and 'bin' columns")
        return
    
    # Create target directory
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📁 Target directory: {TARGET_DIR}")
    print()
    
    # Group submissions by bin
    grouped = df.groupby('bin')
    
    print(f"🗂️  Found {len(grouped)} unique bins")
    print()
    
    # Statistics
    total_copied = 0
    total_skipped = 0
    
    # Process each bin
    for bin_num, group in grouped:
        group_name = f"Group{int(bin_num)}"
        group_dir = TARGET_DIR / group_name
        group_dir.mkdir(exist_ok=True)
        
        print(f"📦 Processing {group_name} ({len(group)} submissions)...")
        
        for idx, row in group.iterrows():
            submission_key = str(row['submission_key'])
            source_path = SOURCE_DIR / submission_key
            target_path = group_dir / submission_key
            
            if source_path.exists() and source_path.is_dir():
                if target_path.exists():
                    print(f"   ⚠️  Skipping {submission_key} (already exists)")
                    total_skipped += 1
                else:
                    shutil.copytree(source_path, target_path)
                    print(f"   ✅ Copied {submission_key}")
                    total_copied += 1
            else:
                print(f"   ❌ Source not found: {submission_key}")
                total_skipped += 1
        
        print()
    
    print("=" * 80)
    print(f"✅ Organization complete!")
    print(f"   Total copied: {total_copied}")
    print(f"   Total skipped: {total_skipped}")
    print(f"   Groups created: {len(grouped)}")
    print("=" * 80)

if __name__ == '__main__':
    main()
