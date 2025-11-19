#!/usr/bin/env python3
"""
Parse all submissions with flexible report detection.
Checks for:
- report.txt (standard)
- Any .txt file in root
- Any .pdf file in root
- Extracts student ID from first line or filename
"""

import os
import csv
import re
from pathlib import Path

SUBMISSIONS_BASE = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/assignment_7153640_export"
OUTPUT_CSV = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/results/submissions_list.csv"

def find_report_file(folder_path):
    """Find any report file (txt or pdf) in submission folder (including subdirs)."""
    # First try standard report.txt in root
    report_txt = os.path.join(folder_path, 'report.txt')
    if os.path.exists(report_txt):
        return report_txt, 'txt', 'report.txt'
    
    # Look for any .txt file or common typos in root (excluding CMakeLists.txt)
    try:
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            # Skip CMakeLists.txt as it's not a report
            if file.lower() == 'cmakelists.txt':
                continue
            # Check for .txt or common typos like .rxt, .tzt, .txr
            if (file.endswith('.txt') or file.endswith(('.rxt', '.tzt', '.txr'))) and os.path.isfile(file_path):
                return file_path, 'txt', file
    except:
        pass
    
    # Look for any .pdf file in root
    try:
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if file.endswith('.pdf') and os.path.isfile(file_path):
                return file_path, 'pdf', file
    except:
        pass
    
    # Look recursively in subdirectories (up to 2 levels deep)
    try:
        for root, dirs, files in os.walk(folder_path):
            depth = root[len(folder_path):].count(os.sep)
            if depth > 2:  # Limit depth
                continue
            
            # Priority: report.txt
            if 'report.txt' in files:
                return os.path.join(root, 'report.txt'), 'txt', f'{os.path.basename(root)}/report.txt'
            
            # Then: any .txt file (excluding CMakeLists.txt)
            for file in files:
                if file.lower() == 'cmakelists.txt':
                    continue
                if file.endswith('.txt'):
                    return os.path.join(root, file), 'txt', f'{os.path.basename(root)}/{file}'
            
            # Then: any .pdf file
            for file in files:
                if file.endswith('.pdf'):
                    return os.path.join(root, file), 'pdf', f'{os.path.basename(root)}/{file}'
    except:
        pass
    
    return None, None, None

def extract_student_id_from_file(file_path, file_type):
    """Extract student ID from report file (txt or pdf)."""
    try:
        if file_type == 'txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                
                # Clean up common prefixes
                if 'Even though' in first_line or 'taken help' in first_line:
                    # Try second line
                    second_line = f.readline().strip()
                    if second_line and (second_line[0].isdigit() or ',' in second_line):
                        return second_line
                    return 'NO_ID'
                
                # If it starts with digits or has comma, likely student ID
                if first_line and (first_line[0].isdigit() or ',' in first_line):
                    return first_line
                
                # Try to find student IDs in first few lines
                f.seek(0)
                for i, line in enumerate(f):
                    if i > 10:  # Check first 10 lines
                        break
                    line = line.strip()
                    # Look for patterns like 2023CS10123 or multiple IDs
                    if re.search(r'\b20\d{2}[A-Z]{2}\d{5}\b', line):
                        return line
                
                return 'NO_ID'
                
        elif file_type == 'pdf':
            # For PDF, we'll note it exists but can't easily extract text
            # Students who submitted PDF should have student ID in filename or we mark it
            return 'PDF_FILE'
    except Exception as e:
        return f'ERROR: {str(e)}'

def detect_submission_type(folder_path):
    """Detect if submission is Python, C++, or mixed."""
    has_python = False
    has_cpp = False
    
    for root, dirs, files in os.walk(folder_path):
        # Skip common non-code directories
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', 'node_modules']]
        
        for file in files:
            if 'student_agent' in file.lower():
                if file.endswith('.py'):
                    has_python = True
                elif file.endswith(('.cpp', '.cxx', '.cc', '.h', '.hpp')):
                    has_cpp = True
    
    if has_python and has_cpp:
        return 'mixed'
    elif has_python:
        return 'python'
    elif has_cpp:
        return 'cpp'
    else:
        return 'unknown'

def check_forbidden_imports_in_file(file_path):
    """Check for forbidden imports in Python files."""
    # PyTorch is now ALLOWED - removed from forbidden list
    forbidden = ['tensorflow', 'keras', 'sklearn', 'cv2', 'opencv', 
                 'pandas', 'matplotlib', 'seaborn', 'plotly']
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            found = [lib for lib in forbidden if lib in content]
            return found
    except:
        return []

def check_forbidden_imports(folder_path, submission_type):
    """Check for forbidden imports in submission."""
    if submission_type not in ['python', 'mixed']:
        return []
    
    forbidden_found = []
    
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                found = check_forbidden_imports_in_file(file_path)
                forbidden_found.extend(found)
    
    # Remove duplicates
    return list(set(forbidden_found))

def scan_submissions():
    """Scan all submissions and create CSV."""
    submissions = []
    
    print(f"Scanning submissions in: {SUBMISSIONS_BASE}")
    print(f"{'='*80}\n")
    
    for folder in sorted(os.listdir(SUBMISSIONS_BASE)):
        folder_path = os.path.join(SUBMISSIONS_BASE, folder)
        
        if not os.path.isdir(folder_path) or folder.startswith('.'):
            continue
        
        print(f"Processing: {folder}")
        
        # Find report file (txt or pdf)
        report_path, file_type, filename = find_report_file(folder_path)
        
        if report_path:
            student_id = extract_student_id_from_file(report_path, file_type)
            has_report = True
            report_file_found = filename
            print(f"  ✓ Found: {filename} (type: {file_type})")
        else:
            student_id = 'NO_REPORT'
            has_report = False
            report_file_found = 'NONE'
            print(f"  ✗ No report file found")
        
        # Detect submission type
        sub_type = detect_submission_type(folder_path)
        
        # Check for CMakeLists.txt
        has_cmake = os.path.exists(os.path.join(folder_path, 'CMakeLists.txt'))
        
        # Check for forbidden imports
        forbidden = check_forbidden_imports(folder_path, sub_type)
        forbidden_str = ','.join(forbidden) if forbidden else 'NONE'
        
        print(f"  ID: {student_id}, Type: {sub_type}, Report: {report_file_found}, Forbidden: {forbidden_str}")
        
        submissions.append({
            'folder_name': folder,
            'student_id': student_id,
            'type': sub_type,
            'has_report': has_report,
            'report_file': report_file_found,
            'has_cmake': has_cmake,
            'forbidden_imports': forbidden_str,
            'status': 'pending',
            'compilation_status': 'not_tested',
            'score_vs_random': '',
            'errors': '',
            'duplicate_of': ''
        })
    
    # Detect duplicates - keep later submission (higher submission number)
    student_id_map = {}
    for sub in submissions:
        sid = sub['student_id']
        if sid not in ['NO_REPORT', 'NO_ID', 'PDF_FILE']:
            if sid not in student_id_map:
                student_id_map[sid] = []
            student_id_map[sid].append(sub)
    
    # Mark duplicates
    for sid, subs in student_id_map.items():
        if len(subs) > 1:
            # Sort by submission number (higher = later)
            subs_sorted = sorted(subs, key=lambda x: x['folder_name'])
            # Mark all except the last one as duplicates
            for i in range(len(subs_sorted) - 1):
                latest_folder = subs_sorted[-1]['folder_name']
                subs_sorted[i]['duplicate_of'] = latest_folder
                print(f"  🔄 Duplicate: {subs_sorted[i]['folder_name']} -> keeping {latest_folder}")
    
    # Write CSV
    with open(OUTPUT_CSV, 'w', newline='') as f:
        fieldnames = ['folder_name', 'student_id', 'type', 'has_report', 'report_file', 
                      'has_cmake', 'forbidden_imports', 'status', 'compilation_status', 
                      'score_vs_random', 'errors', 'duplicate_of']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(submissions)
    
    print(f"\n✅ CSV created: {OUTPUT_CSV}")
    print(f"Total submissions: {len(submissions)}")
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total: {len(submissions)}")
    
    by_type = {}
    for s in submissions:
        by_type[s['type']] = by_type.get(s['type'], 0) + 1
    
    for t, count in sorted(by_type.items()):
        print(f"{t.capitalize()}: {count}")
    
    no_report = sum(1 for s in submissions if not s['has_report'])
    print(f"No report file: {no_report}")
    
    pdf_reports = sum(1 for s in submissions if s['report_file'].endswith('.pdf'))
    print(f"PDF reports: {pdf_reports}")
    
    with_forbidden = sum(1 for s in submissions if s['forbidden_imports'] != 'NONE')
    print(f"With forbidden imports: {with_forbidden}")
    
    duplicates = sum(1 for s in submissions if s['duplicate_of'] != '')
    print(f"Duplicate submissions (will be skipped): {duplicates}")

if __name__ == "__main__":
    scan_submissions()
