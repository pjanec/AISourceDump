#!/usr/bin/env python3

"""
dump.py: The Smart Source Code Dumper

A command-line tool that scans directories and concatenates source files
into a single text file, using a powerful .gitignore-style filtering system.

This script implements a Two-Stage Filter:
1.  Stage 1 (User Rules): .dumpignore, --rule, --filter-file
    Uses '+', '!', and 'exclude' patterns to create an explicit list.
2.  Stage 2 (Project Ignores): .gitignore
    Filters the results from Stage 1, unless a '!' (force) rule was used.
    Now supports HIERARCHICAL .gitignore files (nested in subfolders).
"""

import os
import sys
import argparse
import pathspec
import re
from collections import deque
from enum import Enum, auto 
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

# --- Stats and Helpers ---

class Stats:
    """A simple class to hold statistics for the dump."""
    def __init__(self):
        self.scanned_files = 0
        self.included_files = 0
        self.skipped_files = 0

    def print_summary(self, file_path, total_bytes, dry_run=False):
        """Prints the final summary to stderr."""
        print("\n" + ("-" * 20) + " Dump Summary " + ("-" * 20), file=sys.stderr)
        if dry_run:
            print("Mode:           --dry-run (no file written)", file=sys.stderr)
        else:
            print(f"Output File:    {file_path}", file=sys.stderr)
            if os.path.exists(file_path):
                 print(f"File Size:      {human_readable_size(total_bytes)}", file=sys.stderr)
            else:
                 print("File Size:      0 B (File not created or empty)", file=sys.stderr)

        print(f"Files Included: {self.included_files}", file=sys.stderr)
        print(f"Files Skipped:  {self.skipped_files}", file=sys.stderr)
        print(f"Total Scanned:  {self.scanned_files}", file=sys.stderr)
        print("-" * 54, file=sys.stderr)

def human_readable_size(size, decimal_places=2):
    """Returns the human-readable file size."""
    if size == 0:
        return "0 B"
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

# --- New Enum for Filter Logic ---
class FilterOutcome(Enum):
    """Represents the outcome of the Stage 1 filter."""
    FORCE_INCLUDE = auto()    # Matched a '!' rule
    ADDITIVE_INCLUDE = auto() # Matched a '+' rule
    EXPLICIT_EXCLUDE = auto() # Matched a 'exclude' rule (e.g., *, *.log)
    DEFAULT_INCLUDE = auto()  # No rule matched

# --- Git & Filesystem ---

_git_root_cache = {}

def find_git_root(start_path):
    """Finds the git repository root by searching upwards for a .git directory."""
    abs_start_path = os.path.abspath(start_path)
    
    for cached_path, root in _git_root_cache.items():
        if abs_start_path.startswith(cached_path):
            return root

    path = abs_start_path
    while True:
        if os.path.isdir(os.path.join(path, '.git')):
            _git_root_cache[abs_start_path] = path
            return path
        
        parent = os.path.dirname(path)
        if parent == path:
            _git_root_cache[abs_start_path] = None
            return None
        path = parent

def find_root_gitignore(start_path):
    """Finds the .gitignore file in the git root, if it exists."""
    git_root = find_git_root(start_path)
    if git_root:
        gitignore_path = os.path.join(git_root, '.gitignore')
        if os.path.isfile(gitignore_path):
            return gitignore_path
    return None

def load_rules_from_file(file_path):
    """
    Safely reads a .gitignore-style file and returns a list of rules.
    """
    if not file_path or not os.path.isfile(file_path):
        return []
    
    rules = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    rules.append(line)
    except Exception as e:
        print(f"Warning: Could not read rules from {file_path}. Error: {e}", file=sys.stderr)
    return rules

def get_unique_output_filename(base_path):
    """Finds an available output filename."""
    if not os.path.splitext(base_path)[1]:
        base_path += '.txt'

    base, ext = os.path.splitext(base_path)
    directory = os.path.dirname(base) or '.'
    filename_base = os.path.basename(base)
    
    pattern = re.compile(fr"^{re.escape(filename_base)}(?:_(\d+))?{re.escape(ext)}$")
    
    max_num = -1
    base_file_exists = False

    try:
        for filename in os.listdir(directory):
            match = pattern.match(filename)
            if match:
                if match.group(1):
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                else:
                    base_file_exists = True
    except FileNotFoundError:
        return base_path

    if not base_file_exists and max_num == -1:
        return base_path
    
    if base_file_exists and max_num == -1:
        max_num = 0

    next_num = max_num + 1
    return f"{base}_{next_num}{ext}"

def load_allowed_extensions(exts_file_path):
    """Loads the list of allowed file extensions from a file."""
    if not exts_file_path:
        return None

    print(f"Loading allowed extensions from: {exts_file_path}", file=sys.stderr)
    try:
        extensions = set()
        with open(exts_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip().lower()
                if not line or line.startswith('#'):
                    continue
                if not line.startswith('.'):
                    line = '.' + line
                extensions.add(line)
        
        if not extensions:
            print(f"Warning: Extension file '{exts_file_path}' was empty. Including all file extensions.", file=sys.stderr)
            return None
        return extensions
    except FileNotFoundError:
        print(f"Error: Extensions file '{exts_file_path}' not found. Aborting.", file=sys.stderr)
        sys.exit(1)

# --- New Core Filter Logic ---

def compile_stage_1_rules(rules_list):
    """Compiles a list of rule strings into (pattern, outcome) tuples."""
    compiled_rules = []
    for rule_line in rules_list:
        try:
            if rule_line.startswith('!'):
                pattern_str = rule_line[1:].strip()
                outcome = FilterOutcome.FORCE_INCLUDE
            elif rule_line.startswith('+'):
                pattern_str = rule_line[1:].strip()
                outcome = FilterOutcome.ADDITIVE_INCLUDE
            elif rule_line.startswith('-'):
                pattern_str = rule_line[1:].strip() 
                outcome = FilterOutcome.EXPLICIT_EXCLUDE
            else:
                pattern_str = rule_line
                outcome = FilterOutcome.EXPLICIT_EXCLUDE
            
            pattern = GitWildMatchPattern(pattern_str)
            compiled_rules.append((pattern, outcome, rule_line))
        except Exception as e:
            print(f"Warning: Invalid filter rule '{rule_line}' ignored. Error: {e}", file=sys.stderr)
    return compiled_rules

def get_stage_1_outcome(file_path, compiled_stage_1_rules):
    """Finds the last matching Stage 1 rule for a file."""
    winning_outcome = FilterOutcome.DEFAULT_INCLUDE
    winning_rule = None

    for pattern, outcome, rule_line in compiled_stage_1_rules:
        if pattern.match_file(file_path):
            winning_outcome = outcome
            winning_rule = rule_line
            
    return winning_outcome, winning_rule

def check_nested_gitignore(file_abs_path, current_dir_abs, gitignore_specs_map):
    """
    Checks if a file is ignored by any .gitignore in the directory hierarchy
    starting from current_dir_abs up to the root.
    
    Returns: True if ignored, False otherwise.
    """
    # We walk UP the tree from the file's directory to the root
    # asking each .gitignore we find if it matches the file relative to THAT .gitignore.
    
    check_path = current_dir_abs
    while True:
        spec = gitignore_specs_map.get(check_path)
        if spec:
            # Calculate path relative to this specific .gitignore location
            rel_path = os.path.relpath(file_abs_path, check_path)
            # Note: match_file returns True if the file is IGNORED
            if spec.match_file(rel_path):
                return True
        
        parent = os.path.dirname(check_path)
        if parent == check_path: # Hit filesystem root
            break
        # Stop if we go above the execution root (optional, but safer)
        # But keeping it open allows finding gitignores in parent dirs
        check_path = parent
        
    return False

# --- Core Logic ---

def build_static_rulesets(args, root_dir):
    """Builds the two separate rulesets for 'Explicit Filter Mode'."""
    
    # --- Build Stage 1 Ruleset (User Rules) ---
    stage_1_rules = []
    if args.rule:
        print("Using rules from --rule arguments.", file=sys.stderr)
        stage_1_rules.extend(args.rule)
    elif args.filter_file:
        print("Using rules from --filter-file arguments.", file=sys.stderr)
        for f in args.filter_file:
            stage_1_rules.extend(load_rules_from_file(f))
            
    compiled_stage_1_rules = compile_stage_1_rules(stage_1_rules)
    
    # --- Build Stage 2 Ruleset (Project Ignores) ---
    stage_2_gitignore_spec = None
    if not args.no_gitignore:
        gitignore_path = find_root_gitignore(root_dir)
        if gitignore_path:
            gitignore_rules = load_rules_from_file(gitignore_path)
            if gitignore_rules:
                stage_2_gitignore_spec = pathspec.PathSpec.from_lines(
                    'gitwildmatch',
                    gitignore_rules
                )

    return compiled_stage_1_rules, stage_2_gitignore_spec

def write_file_content(outfile, file_path, header_path):
    """Writes a single file's content to the main output file."""
    outfile.write('\n')
    outfile.write(f'//{"=" * 80}\n')
    outfile.write(f'// File: {header_path}\n')
    outfile.write(f'//{"=" * 80}\n\n')
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
            outfile.write(infile.read())
            outfile.write('\n')
        outfile.flush()
    except Exception as e:
        outfile.write(f"// Error reading file: {e}\n\n")
        print(f"Warning: Could not read file {file_path}. Error: {e}", file=sys.stderr)

def process_file(
    f, f_path, root, 
    compiled_stage_1_rules, 
    gitignore_specs_map, # CHANGED: Now accepts a map of dir -> spec
    allowed_extensions, 
    processed_files, 
    stats, 
    args, 
    outfile
):
    """Processes a single file using the new Two-Stage Filter logic."""
    stats.scanned_files += 1

    if f_path in processed_files:
        return

    # --- STAGE 1: User Rules (.dumpignore, --rule, --filter-file) ---
    stage_1_outcome, winning_rule = get_stage_1_outcome(f_path, compiled_stage_1_rules)

    # --- STAGE 2: Project Ignores (.gitignore) ---
    # We only run Stage 2 if Stage 1 resulted in an Additive or Default include.
    is_ignored_by_stage_2 = False
    if stage_1_outcome in (FilterOutcome.ADDITIVE_INCLUDE, FilterOutcome.DEFAULT_INCLUDE):
        if gitignore_specs_map:
            abs_file_path = os.path.join(root, f)
            abs_root_path = os.path.abspath(root)
            is_ignored_by_stage_2 = check_nested_gitignore(abs_file_path, abs_root_path, gitignore_specs_map)

    # --- STAGE 3: Extension Filter (Optional) ---
    ext_matched = True
    if allowed_extensions is not None:
        file_ext = os.path.splitext(f)[1].lower()
        if not file_ext or file_ext not in allowed_extensions:
            ext_matched = False

    # --- FINAL DECISION ---
    
    # 1. Check for Force Include (bypasses all other checks)
    if stage_1_outcome == FilterOutcome.FORCE_INCLUDE:
        if ext_matched:
            stats.included_files += 1
            if args.debug:
                print(f"[INCLUDE] {f_path} (matched rule: {winning_rule})", file=sys.stderr)
            
            if not args.dry_run:
                full_path = os.path.join(root, f)
                write_file_content(outfile, full_path, f_path)
                processed_files.add(f_path)
        else:
            stats.skipped_files += 1
            if args.debug:
                print(f"[SKIP]    {f_path} (matched rule: {winning_rule}, but extension mismatch)", file=sys.stderr)
        return

    # 2. Check for Explicit Exclude
    if stage_1_outcome == FilterOutcome.EXPLICIT_EXCLUDE:
        stats.skipped_files += 1
        if args.debug:
            print(f"[SKIP]    {f_path} (matched rule: {winning_rule})", file=sys.stderr)
        return

    # 3. Check for Stage 2 (gitignore) Ignore
    if is_ignored_by_stage_2:
        stats.skipped_files += 1
        if args.debug:
            print(f"[SKIP]    {f_path} (ignored by .gitignore)", file=sys.stderr)
        return

    # 4. Check for Extension Filter
    if not ext_matched:
        stats.skipped_files += 1
        if args.debug:
            print(f"[SKIP]    {f_path} (extension mismatch)", file=sys.stderr)
        return

    # 5. Include
    stats.included_files += 1
    if args.debug:
        if stage_1_outcome == FilterOutcome.ADDITIVE_INCLUDE:
            print(f"[INCLUDE] {f_path} (matched rule: {winning_rule})", file=sys.stderr)
        else: 
            print(f"[INCLUDE] {f_path} (included by default)", file=sys.stderr)
    
    if not args.dry_run:
        full_path = os.path.join(root, f)
        write_file_content(outfile, full_path, f_path)
        processed_files.add(f_path)

def walk_and_process_static(
    outfile, input_dirs, root_dir, 
    compiled_stage_1_rules, 
    stage_2_gitignore_spec,
    allowed_extensions, stats, args,
    is_explicit_mode=False
):
    """Processes files using a static set of rules."""
    processed_files = set()
    
    # Compatibility wrapper for new process_file signature
    # Map the root dir to the single static spec
    gitignore_map = {}
    if stage_2_gitignore_spec:
        # We associate the static spec with the root directory for matching purposes
        # But ideally, static mode assumes one gitignore at the root.
        gitignore_map[os.path.abspath(root_dir)] = stage_2_gitignore_spec

    for input_dir in input_dirs:
        abs_input_dir = os.path.abspath(input_dir)
        if not os.path.isdir(abs_input_dir):
            print(f"Warning: '{input_dir}' is not a valid directory. Skipping.", file=sys.stderr)
            continue
            
        for root, dirs, files in os.walk(abs_input_dir, topdown=True):
            # --- FIX 1: Hard Exclude .git ---
            if '.git' in dirs:
                dirs.remove('.git')
                if args.debug:
                    print(f"[SKIP]    Skipping .git directory in {root}", file=sys.stderr)

            rel_root = os.path.relpath(root, root_dir).replace("\\", "/")
            dir_paths = [f"{rel_root}/{d}/" if rel_root != '.' else f"{d}/" for d in dirs]
            file_paths = [f"{rel_root}/{f}" if rel_root != '.' else f"{f}" for f in files]

            temp_dirs = []
            for d, d_path in zip(dirs, dir_paths):
                stage_1_outcome, winning_rule = get_stage_1_outcome(d_path, compiled_stage_1_rules)
                
                if (not is_explicit_mode) and (stage_1_outcome == FilterOutcome.EXPLICIT_EXCLUDE):
                    stats.scanned_files += 1 
                    stats.skipped_files += 1
                    if args.debug:
                        print(f"[SKIP]    {d_path} (matched rule: {winning_rule})", file=sys.stderr)
                else:
                    temp_dirs.append(d)
            dirs[:] = temp_dirs

            for f, f_path in zip(files, file_paths):
                process_file(
                    f, f_path, root, 
                    compiled_stage_1_rules, 
                    gitignore_map, # Pass the map
                    allowed_extensions, processed_files, stats, args, outfile
                )

def walk_and_process_hierarchical(
    outfile, input_dirs, root_dir, 
    base_compiled_stage_1_rules,
    root_gitignore_spec,
    allowed_extensions, stats, args
):
    """Processes files using hierarchical .dumpignore and .gitignore files."""
    processed_files = set()
    
    # Cache for Stage 1 (.dumpignore)
    rules_cache = {root_dir: base_compiled_stage_1_rules}
    raw_rules_cache = {root_dir: []}
    
    # Cache for Stage 2 (.gitignore) - Map AbsDir -> PathSpec
    gitignore_specs_map = {}
    if root_gitignore_spec:
        # Attempt to map the initial spec to the root dir
        # Note: find_root_gitignore might return a path higher up than root_dir
        # We map it to the directory containing the gitignore file
        git_root_path = find_git_root(root_dir)
        if git_root_path:
             gitignore_specs_map[git_root_path] = root_gitignore_spec

    for input_dir in input_dirs:
        abs_input_dir = os.path.abspath(input_dir)
        if not os.path.isdir(abs_input_dir):
            print(f"Warning: '{input_dir}' is not a valid directory. Skipping.", file=sys.stderr)
            continue

        for root, dirs, files in os.walk(abs_input_dir, topdown=True):
            # --- FIX 1: Hard Exclude .git ---
            if '.git' in dirs:
                dirs.remove('.git')
                if args.debug:
                     print(f"[SKIP]    Skipping .git directory in {root}", file=sys.stderr)

            # --- Handle Stage 1 (.dumpignore) Hierarchy ---
            parent_dir = os.path.dirname(root)
            if root == root_dir or root == abs_input_dir:
                 parent_compiled_rules = base_compiled_stage_1_rules
                 parent_raw_rules = [] 
            else:
                 parent_compiled_rules = rules_cache.get(parent_dir, base_compiled_stage_1_rules)
                 parent_raw_rules = raw_rules_cache.get(parent_dir, [])

            current_compiled_rules = parent_compiled_rules
            current_raw_rules = parent_raw_rules
            
            if not args.no_dumpignore:
                dumpignore_path = os.path.join(root, '.dumpignore')
                if os.path.isfile(dumpignore_path):
                    new_rules = load_rules_from_file(dumpignore_path)
                    if new_rules:
                        current_raw_rules = parent_raw_rules + new_rules
                        current_compiled_rules = compile_stage_1_rules(current_raw_rules)
            
            rules_cache[root] = current_compiled_rules
            raw_rules_cache[root] = current_raw_rules
            
            # --- Handle Stage 2 (.gitignore) Hierarchy ---
            if not args.no_gitignore:
                gitignore_path = os.path.join(root, '.gitignore')
                if os.path.isfile(gitignore_path):
                    new_git_rules = load_rules_from_file(gitignore_path)
                    if new_git_rules:
                        if args.debug:
                            print(f"Loaded .gitignore from {gitignore_path}", file=sys.stderr)
                        spec = pathspec.PathSpec.from_lines('gitwildmatch', new_git_rules)
                        gitignore_specs_map[root] = spec

            # Paths for output/debug
            rel_root = os.path.relpath(root, root_dir).replace("\\", "/")
            dir_paths = [f"{rel_root}/{d}/" if rel_root != '.' else f"{d}/" for d in dirs]
            file_paths = [f"{rel_root}/{f}" if rel_root != '.' else f"{f}" for f in files]

            # --- Filter directories ---
            temp_dirs = []
            for d, d_path in zip(dirs, dir_paths):
                stage_1_outcome, winning_rule = get_stage_1_outcome(d_path, current_compiled_rules)
                
                if stage_1_outcome == FilterOutcome.EXPLICIT_EXCLUDE:
                    stats.scanned_files += 1
                    stats.skipped_files += 1
                    if args.debug:
                        print(f"[SKIP]    {d_path} (matched rule: {winning_rule})", file=sys.stderr)
                else:
                    temp_dirs.append(d)
            dirs[:] = temp_dirs

            # --- Filter and process files ---
            for f, f_path in zip(files, file_paths):
                process_file(
                    f, f_path, root, 
                    current_compiled_rules, 
                    gitignore_specs_map, # Pass the FULL map
                    allowed_extensions, processed_files, stats, args, outfile
                )


def collect_source_files(args, root_dir):
    """Main orchestrator."""
    stats = Stats()

    if os.path.isabs(args.output_file):
        final_base_path = args.output_file
    else:
        final_base_path = os.path.join(".dumps", args.output_file)

    output_directory = os.path.dirname(final_base_path)
    if output_directory and not args.dry_run:
        os.makedirs(output_directory, exist_ok=True)

    output_file = get_unique_output_filename(final_base_path)
    if args.dry_run:
        print("Running in --dry-run mode. No output file will be written.", file=sys.stderr)
    else:
        print(f"Output will be written to {output_file}", file=sys.stderr)
    
    allowed_extensions = load_allowed_extensions(args.exts)
    
    try:
        is_explicit_mode = args.rule or args.filter_file
        
        with open(os.devnull, 'w') if args.dry_run else open(output_file, 'w', encoding='utf-8') as outfile:
            
            if is_explicit_mode:
                if args.debug:
                    print("Running in Explicit Filter Mode.", file=sys.stderr)
                compiled_stage_1_rules, stage_2_gitignore_spec = build_static_rulesets(args, root_dir)
                walk_and_process_static(
                    outfile, args.input_dirs, root_dir,
                    compiled_stage_1_rules, stage_2_gitignore_spec,
                    allowed_extensions, stats, args, is_explicit_mode=True
                )
            else:
                if args.debug:
                    print("Running in Hierarchical Mode (Default).", file=sys.stderr)
                
                base_compiled_stage_1_rules = []
                root_gitignore_spec = None
                if not args.no_gitignore:
                    gitignore_path = find_root_gitignore(root_dir)
                    if gitignore_path:
                         gitignore_rules = load_rules_from_file(gitignore_path)
                         if gitignore_rules:
                            root_gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_rules)
                
                walk_and_process_hierarchical(
                    outfile, args.input_dirs, root_dir,
                    base_compiled_stage_1_rules, root_gitignore_spec,
                    allowed_extensions, stats, args
                )

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        if not args.dry_run and os.path.exists(output_file) and os.path.getsize(output_file) == 0:
            os.remove(output_file)
        sys.exit(1)

    total_bytes = 0
    if not args.dry_run and os.path.exists(output_file):
        total_bytes = os.path.getsize(output_file)
        
    stats.print_summary(output_file, total_bytes, args.dry_run)
    
    if not args.dry_run and total_bytes == 0 and os.path.exists(output_file):
        print("\nWarning: No matching files were found to process.", file=sys.stderr)
        os.remove(output_file)
    elif args.dry_run:
        print("Dry run finished.", file=sys.stderr)
    else:
        print(f"\nDone. Output successfully written to {output_file}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="dump.py: The Smart Source Code Dumper.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("input_dirs", nargs='+', help="Input directories to scan.")
    parser.add_argument("output_file", help="Output filename.")
    parser.add_argument("--filter-file", action="append", metavar="<path>", help=".dumpignore-style file.")
    parser.add_argument("--rule", action="append", metavar="<pattern>", help="Single filter rule.")
    parser.add_argument("--no-gitignore", action="store_true", help="Disable .gitignore loading.")
    parser.add_argument("--no-dumpignore", action="store_true", help="Disable .dumpignore loading.")
    parser.add_argument("--exts", metavar="<path>", help="Allowed extensions file.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose logging.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing output.")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    args = parser.parse_args()
    root_dir = os.path.abspath(os.getcwd())
    collect_source_files(args, root_dir)

if __name__ == "__main__":
    main()