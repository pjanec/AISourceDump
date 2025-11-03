#!/usr/bin/env python3

"""
dump.py: The Smart Source Code Dumper

A command-line tool that scans directories and concatenates source files
into a single text file, using a powerful .gitignore-style filtering system.

This script can be run in two modes:
1.  Hierarchical Mode (Default):
    Behaves like git, respecting .gitignore and searching for
    .dumpignore files in every subdirectory.

2.  Explicit Filter Mode (Static):
    Triggered by --rule or --filter-file. Uses a single, static
    ruleset, ignoring all .dumpignore files found in the filesystem.
"""

import os
import sys
import argparse
import pathspec
import re
from collections import deque
# Import the pattern matcher we'll use for manual debug checks
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
        print(f"Loaded {len(rules)} rules from {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not read rules from {file_path}. Error: {e}", file=sys.stderr)
    return rules

def get_unique_output_filename(base_path):
    """
    Finds an available output filename (e.g., dump.txt, dump_1.txt).
    """
    if not os.path.splitext(base_path)[1]:
        base_path += '.txt'

    base, ext = os.path.splitext(base_path)
    directory = os.path.dirname(base) or '.'
    filename_base = os.path.basename(base)
    
    # Regex to match 'filename_base.ext' or 'filename_base_NUMBER.ext'
    # Use a raw f-string (fr"...") to avoid SyntaxWarning with \d
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
    """
    Loads the list of allowed file extensions from a file.
    """
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
        
        print(f"Allowed extensions: {', '.join(extensions)}", file=sys.stderr)
        return extensions
    except FileNotFoundError:
        print(f"Error: Extensions file '{exts_file_path}' not found. Aborting.", file=sys.stderr)
        sys.exit(1)

# --- Core Logic ---

def build_static_ruleset(args, root_dir):
    """
    Builds a single, static PathSpec for "Explicit Filter Mode"
    and returns the spec and the rules.
    """
    rules = []
    
    # 1. Load .gitignore (unless disabled)
    if not args.no_gitignore:
        gitignore_path = find_root_gitignore(root_dir)
        if gitignore_path:
            rules.extend(load_rules_from_file(gitignore_path))
    
    # 2. Load rules from --rule or --filter-file
    if args.rule:
        print("Using rules from --rule arguments.", file=sys.stderr)
        rules.extend(args.rule)
    elif args.filter_file:
        print("Using rules from --filter-file arguments.", file=sys.stderr)
        for f in args.filter_file:
            rules.extend(load_rules_from_file(f))
            
    return pathspec.PathSpec.from_lines('gitwildmatch', rules), rules

def write_file_content(outfile, file_path, header_path):
    """
    Writes a single file's content to the main output file
    with a standardized header.
    """
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
    f, f_path, root, current_spec, current_rules,
    allowed_extensions, processed_files, stats, args, outfile
):
    """
    Processes a single file: checks all filters, updates stats,
    and writes to the output file if all checks pass.
    """
    stats.scanned_files += 1

    if f_path in processed_files:
        if args.debug:
            print(f"[SKIP]    {f_path} (already processed)", file=sys.stderr)
        return

    # 1. Perform spec match
    is_ignored = current_spec.match_file(f_path)
    is_included = not is_ignored
    rule_pattern = None

    # 2. If in debug mode, manually find the "winning" rule
    #    This is slower, but provides the reason.
    if args.debug and current_rules: # Only if there are rules
        for rule_line in reversed(current_rules):
            try:
                # Compile a single pattern
                pattern = GitWildMatchPattern(rule_line)
                # Check if this rule matches the file
                if pattern.match_file(f_path):
                    rule_pattern = rule_line
                    break # Found the last matching rule
            except Exception:
                # Ignore invalid patterns, etc.
                pass
    
    # 3. Check extensions
    ext_matched = True
    if allowed_extensions is not None:
        file_ext = os.path.splitext(f)[1].lower()
        if not file_ext or file_ext not in allowed_extensions:
            ext_matched = False

    # 4. Final Decision
    if is_included and ext_matched:
        # INCLUSION
        stats.included_files += 1
        if args.debug:
            if rule_pattern and rule_pattern.startswith('!'):
                print(f"[INCLUDE] {f_path} (matched rule: {rule_pattern})", file=sys.stderr)
            else:
                print(f"[INCLUDE] {f_path} (included by default)", file=sys.stderr)
        
        if not args.dry_run:
            full_path = os.path.join(root, f)
            write_file_content(outfile, full_path, f_path)
            processed_files.add(f_path)
    
    else:
        # SKIPPING
        stats.skipped_files += 1
        if args.debug:
            if not is_included: # Skipped by a rule
                if rule_pattern:
                    print(f"[SKIP]    {f_path} (matched rule: {rule_pattern})", file=sys.stderr)
                else:
                    # This can happen if the rule is complex or not found by our manual check
                    print(f"[SKIP]    {f_path} (matched .dumpignore rule)", file=sys.stderr)
            elif not ext_matched:
                print(f"[SKIP]    {f_path} (extension not in --exts list)", file=sys.stderr)
        return

def walk_and_process_static(
    outfile, input_dirs, root_dir, spec, rules,
    allowed_extensions, stats, args
):
    """
    Processes files using a single, static PathSpec.
    """
    processed_files = set()
    
    for input_dir in input_dirs:
        abs_input_dir = os.path.abspath(input_dir)
        if not os.path.isdir(abs_input_dir):
            print(f"Warning: '{input_dir}' is not a valid directory. Skipping.", file=sys.stderr)
            continue
            
        for root, dirs, files in os.walk(abs_input_dir, topdown=True):
            # Paths must be relative to the *root_dir* for the spec to work
            rel_root = os.path.relpath(root, root_dir).replace("\\", "/")
            
            # Create full relative paths for matching
            dir_paths = [f"{rel_root}/{d}/" if rel_root != '.' else f"{d}/" for d in dirs]
            file_paths = [f"{rel_root}/{f}" if rel_root != '.' else f"{f}" for f in files]

            # Filter directories in-place
            ignored_dirs = set()
            if args.debug:
                # Slower, but provides debug info
                temp_dirs = []
                for d, d_path in zip(dirs, dir_paths):
                    is_ignored = spec.match_file(d_path)
                    
                    if is_ignored:
                        ignored_dirs.add(d_path)
                        stats.scanned_files += 1 # Count dir as scanned
                        stats.skipped_files += 1
                        
                        # Find the matching rule for debug
                        rule_pattern = None
                        if rules:
                            for rule_line in reversed(rules):
                                try:
                                    pattern = GitWildMatchPattern(rule_line)
                                    if pattern.match_file(d_path):
                                        rule_pattern = rule_line
                                        break
                                except Exception: pass
                        
                        if rule_pattern:
                            print(f"[SKIP]    {d_path} (matched rule: {rule_pattern})", file=sys.stderr)
                        else:
                            print(f"[SKIP]    {d_path} (matched .dumpignore rule)", file=sys.stderr)
                    else:
                        temp_dirs.append(d)
                dirs[:] = temp_dirs
            else:
                # Faster, no debug info
                ignored_dirs = set(spec.match_files(dir_paths))
                dirs[:] = [d for d, d_path in zip(dirs, dir_paths) if d_path not in ignored_dirs]
            
            # Filter and process files
            for f, f_path in zip(files, file_paths):
                process_file(
                    f, f_path, root, spec, rules,
                    allowed_extensions, processed_files, stats, args, outfile
                )

def walk_and_process_hierarchical(
    outfile, input_dirs, root_dir, base_spec, base_rules,
    allowed_extensions, stats, args
):
    """
    Processes files using hierarchical .dumpignore files,
    recalculating the PathSpec for each directory.
    """
    processed_files = set()
    spec_cache = {} # Cache for directory PathSpecs

    # Pre-warm cache with base spec for the root
    spec_cache[root_dir] = (base_spec, base_rules)
    
    for input_dir in input_dirs:
        abs_input_dir = os.path.abspath(input_dir)
        if not os.path.isdir(abs_input_dir):
            print(f"Warning: '{input_dir}' is not a valid directory. Skipping.", file=sys.stderr)
            continue

        for root, dirs, files in os.walk(abs_input_dir, topdown=True):
            # Find the spec for the parent directory
            parent_dir = os.path.dirname(root)
            if root == root_dir or root == abs_input_dir:
                 parent_spec, parent_rules = base_spec, base_rules
            else:
                 # Should always be in cache from parent's walk
                 parent_spec, parent_rules = spec_cache.get(parent_dir, (base_spec, base_rules)) 

            current_spec, current_rules = parent_spec, parent_rules
            
            # Load .dumpignore from the current directory (if not disabled)
            if not args.no_dumpignore:
                dumpignore_path = os.path.join(root, '.dumpignore')
                if os.path.isfile(dumpignore_path):
                    new_rules = load_rules_from_file(dumpignore_path)
                    if new_rules:
                        # Combine parent spec with new rules
                        current_rules = parent_rules + new_rules
                        current_spec = pathspec.PathSpec.from_lines(
                            'gitwildmatch',
                            current_rules
                        )
            
            # Store the calculated spec for this directory
            spec_cache[root] = (current_spec, current_rules)
            
            # Paths must be relative to the *root_dir* for the spec to work
            rel_root = os.path.relpath(root, root_dir).replace("\\", "/")
            
            dir_paths = [f"{rel_root}/{d}/" if rel_root != '.' else f"{d}/" for d in dirs]
            file_paths = [f"{rel_root}/{f}" if rel_root != '.' else f"{f}" for f in files]

            # Filter directories in-place
            ignored_dirs = set()
            if args.debug:
                # Slower, but provides debug info
                temp_dirs = []
                for d, d_path in zip(dirs, dir_paths):
                    is_ignored = current_spec.match_file(d_path)

                    if is_ignored:
                        ignored_dirs.add(d_path)
                        stats.scanned_files += 1 # Count dir as scanned
                        stats.skipped_files += 1
                        
                        # Find the matching rule for debug
                        rule_pattern = None
                        if current_spec.lines:
                            for rule_line in reversed(current_spec.lines):
                                try:
                                    pattern = GitWildMatchPattern(rule_line)
                                    if pattern.match_file(d_path):
                                        rule_pattern = rule_line
                                        break
                                except Exception: pass

                        if rule_pattern:
                            print(f"[SKIP]    {d_path} (matched rule: {rule_pattern})", file=sys.stderr)
                        else:
                            print(f"[SKIP]    {d_path} (matched .dumpignore rule)", file=sys.stderr)
                    else:
                        temp_dirs.append(d)
                dirs[:] = temp_dirs
            else:
                # Faster, no debug info
                ignored_dirs = set(current_spec.match_files(dir_paths))
                dirs[:] = [d for d, d_path in zip(dirs, dir_paths) if d_path not in ignored_dirs]


            # Filter and process files
            for f, f_path in zip(files, file_paths):
                process_file(
                    f, f_path, root, current_spec, current_rules,
                    allowed_extensions, processed_files, stats, args, outfile
                )


def collect_source_files(args, root_dir):
    """
    Main orchestrator. Determines the mode and calls the
    appropriate walker function.
    """
    stats = Stats()

    # Determine the final base path for the output file
    if os.path.isabs(args.output_file):
        final_base_path = args.output_file
    else:
        final_base_path = os.path.join(".dumps", args.output_file)

    # Ensure the target directory for the output file exists.
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
        # Determine mode
        is_explicit_mode = args.rule or args.filter_file
        
        # Open output file *after* determining mode, in case of arg errors
        with open(os.devnull, 'w') if args.dry_run else open(output_file, 'w', encoding='utf-8') as outfile:
            
            if is_explicit_mode:
                if args.debug:
                    print("Running in Explicit Filter Mode.", file=sys.stderr)
                static_spec, static_rules = build_static_ruleset(args, root_dir)
                walk_and_process_static(
                    outfile,
                    args.input_dirs,
                    root_dir,
                    static_spec,
                    static_rules,
                    allowed_extensions,
                    stats,
                    args
                )
            else:
                if args.debug:
                    print("Running in Hierarchical Mode (Default).", file=sys.stderr)
                base_rules = []
                if not args.no_gitignore:
                    gitignore_path = find_root_gitignore(root_dir)
                    if gitignore_path:
                        base_rules.extend(load_rules_from_file(gitignore_path))
                
                base_spec = pathspec.PathSpec.from_lines('gitwildmatch', base_rules)
                
                walk_and_process_hierarchical(
                    outfile,
                    args.input_dirs,
                    root_dir,
                    base_spec,
                    base_rules,
                    allowed_extensions,
                    stats,
                    args
                )

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        if not args.dry_run and os.path.exists(output_file) and os.path.getsize(output_file) == 0:
            os.remove(output_file)
        sys.exit(1)

    # --- Final Summary ---
    total_bytes = 0
    if not args.dry_run and os.path.exists(output_file):
        total_bytes = os.path.getsize(output_file)
        
    stats.print_summary(output_file, total_bytes, args.dry_run)
    
    # Clean up empty file
    if not args.dry_run and total_bytes == 0 and os.path.exists(output_file):
        print("\nWarning: No matching files were found to process.", file=sys.stderr)
        os.remove(output_file)
        print(f"Removed empty output file: {output_file}", file=sys.stderr)
    elif args.dry_run:
        print("Dry run finished.", file=sys.stderr)
    else:
        print(f"\nDone. Output successfully written to {output_file}", file=sys.stderr)

def main():
    """
    Parses command-line arguments and starts the dump process.
    """
    parser = argparse.ArgumentParser(
        description="dump.py: The Smart Source Code Dumper. Concatenates source files into a single text file, respecting .gitignore and .dumpignore rules.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Usage Examples:

  # 1. Default (Hierarchical) Mode:
  #    Dumps 'src/', respects .gitignore and all .dumpignore files found.
  $ python dump.py src/ my_dump.txt

  # 2. Test Filters (Debug + Dry Run):
  #    See *why* files are being included/skipped without writing any file.
  $ python dump.py . my_dump.txt --debug --dry-run

  # 3. Explicit Mode (Allow-List):
  #    Dumps *only* .py and .md files, respects .gitignore.
  $ python dump.py . my_dump.txt --rule "*" --rule "!*.py" --rule "!*.md"

  # 4. Explicit Mode (Filter File):
  #    Uses rules from 'api.dumpignore', ignores default .dumpignore files.
  $ python dump.py . api_dump.txt --filter-file api.dumpignore

  # 5. Disable .gitignore:
  #    Dumps *everything* from 'src/', ignoring .gitignore.
  $ python dump.py src/ my_dump.txt --no-gitignore
"""
    )
    
    # --- Positional Arguments ---
    parser.add_argument(
        "input_dirs",
        nargs='+',
        help="One or more input directories to scan."
    )
    parser.add_argument(
        "output_file",
        help="The base name for the output file (e.g., 'dump.txt').\n"
             "Will be placed in .dumps/ (if relative) and numbered (dump_1.txt) if it exists."
    )
    
    # --- Filtering Arguments ---
    parser.add_argument(
        "--filter-file",
        action="append",
        metavar="<path>",
        help="Path to a .dumpignore-style file to use for filtering.\n"
             "Can be used multiple times; files are loaded in order.\n"
             "Using this enables 'Explicit Filter Mode'."
    )
    parser.add_argument(
        "--rule",
        action="append",
        metavar="<pattern>",
        help="A single filter rule (e.g., '*.py' or '!*.md').\n"
             "Can be used multiple times.\n"
             "Using this enables 'Explicit Filter Mode' and ignores --filter-file."
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Disable loading rules from .gitignore files."
    )
    parser.add_argument(
        "--no-dumpignore",
        action="store_true",
        help="Disable loading rules from .dumpignore files.\n"
             "In Hierarchical Mode: Disables hierarchical search.\n"
             "In Explicit Mode: Has no effect."
    )
    
    # --- Other Arguments ---
    parser.add_argument(
        "--exts",
        metavar="<path>",
        help="Path to a file listing allowed file extensions (e.g., '.py', 'js').\n"
             "If omitted, all extensions are allowed."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose logging to stderr, showing why each file was included or skipped."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the script without writing any output file. Excellent for testing rules with --debug."
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    args = parser.parse_args()
    
    # Use current working directory as the root for all relative paths
    root_dir = os.path.abspath(os.getcwd())
    
    collect_source_files(args, root_dir)

if __name__ == "__main__":
    main()




