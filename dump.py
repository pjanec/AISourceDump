import os
import sys
import argparse
import pathspec
from collections import deque
import re

# --- Git Root Cache ---
# Caches found git roots to avoid repeated upward searches in subdirectories.
_git_root_cache = {}

def find_git_root(start_path):
    """Finds the git repository root by searching upwards for a .git directory."""
    abs_start_path = os.path.abspath(start_path)
    
    # Check cache first
    for cached_path, root in _git_root_cache.items():
        if abs_start_path.startswith(cached_path):
            return root

    path = abs_start_path
    while True:
        if os.path.isdir(os.path.join(path, '.git')):
            _git_root_cache[abs_start_path] = path
            return path
        
        parent = os.path.dirname(path)
        if parent == path: # Reached filesystem root
            _git_root_cache[abs_start_path] = None
            return None
        path = parent

def get_unique_output_filename(base_path):
    """
    Finds an available output filename. If base_path exists (e.g., dump.txt),
    it scans for existing numbered files (dump_1.txt, dump_123.txt) and creates
    the next one in sequence (dump_124.txt).
    """
    if not os.path.splitext(base_path)[1]:
        base_path += '.txt'

    base, ext = os.path.splitext(base_path)
    directory = os.path.dirname(base) or '.'
    filename_base = os.path.basename(base)
    
    # Regex to match 'filename_base.ext' or 'filename_base_NUMBER.ext'
    pattern = re.compile(f"^{re.escape(filename_base)}(?:_(\d+))?{re.escape(ext)}$")
    
    max_num = -1
    base_file_exists = False

    try:
        for filename in os.listdir(directory):
            match = pattern.match(filename)
            if match:
                if match.group(1): # It's a numbered file
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                else: # It's the base file without a number
                    base_file_exists = True
    except FileNotFoundError:
        # Directory doesn't exist yet, so the original base_path is fine
        return base_path

    if not base_file_exists and max_num == -1:
        # No files with this base name exist yet
        return base_path
    
    # If base file exists but no numbered files, the highest "number" is 0
    if base_file_exists and max_num == -1:
        max_num = 0

    next_num = max_num + 1
    return f"{base}_{next_num}{ext}"

def find_and_load_ignore_files(stop_dir, current_dir, ignore_filenames):
    """
    Walks up from current_dir to stop_dir, loading all specified ignore files found.
    """
    patterns = []
    ignore_files_to_check = deque()
    
    path = current_dir
    while True:
        for filename in reversed(ignore_filenames):
            ignore_file_path = os.path.join(path, filename)
            if os.path.isfile(ignore_file_path):
                ignore_files_to_check.appendleft(ignore_file_path)
        
        if os.path.samefile(path, stop_dir):
            break
        
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
        
    for file_path in ignore_files_to_check:
        with open(file_path, 'r', encoding='utf-8') as f:
            patterns.extend(line.strip() for line in f if line.strip() and not line.strip().startswith('#'))
            
    return patterns

def load_allowed_extensions(exts_file_path):
    """
    Loads the list of allowed file extensions from a file.
    """
    if not exts_file_path:
        print("No --exts file provided. Including all file extensions.")
        return None

    print(f"Loading allowed extensions from: {exts_file_path}")
    try:
        extensions = []
        with open(exts_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if not line.startswith('.'):
                    line = '.' + line
                extensions.append(line.lower())
        
        if not extensions:
            print(f"Warning: Extension file '{exts_file_path}' was empty. Including all file extensions.")
            return None
        
        print(f"Allowed extensions: {', '.join(extensions)}")
        return extensions
    except FileNotFoundError:
        print(f"Error: Extensions file '{exts_file_path}' not found. Aborting.")
        sys.exit(1)

def collect_source_files(input_dirs, output_file_base, ignore_file, use_gitignore, allowed_extensions):
    """
    Walks input directories and concatenates content of specified file types
    into a single output file, using hierarchical ignore files.
    """
    output_file = get_unique_output_filename(output_file_base)
    print(f"Output will be written to {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            for input_dir in input_dirs:
                abs_input_dir = os.path.abspath(input_dir)
                if not os.path.isdir(abs_input_dir):
                    print(f"Warning: '{input_dir}' is not a valid directory. Skipping.")
                    continue

                print(f"\nProcessing directory: {abs_input_dir}")
                
                # Mode 1: --ignore override (highest precedence)
                if ignore_file:
                    print(f"Using specified ignore file: {ignore_file}")
                    try:
                        with open(ignore_file, 'r', encoding='utf-8') as f:
                            patterns = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                        spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)
                        walk_and_process(outfile, abs_input_dir, allowed_extensions, spec=spec)
                    except FileNotFoundError:
                        print(f"Error: Specified ignore file '{ignore_file}' not found. Aborting.")
                        sys.exit(1)
                # Mode 2 & 3: Hierarchical search
                else:
                    if use_gitignore:
                        print("Git compatibility mode enabled: Searching for '.gitignore' and '.dumpignore' files.")
                    else:
                        print("Default mode: Searching for '.dumpignore' files only.")
                    
                    walk_and_process(outfile, abs_input_dir, allowed_extensions, spec=None, use_gitignore=use_gitignore)

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
            os.remove(output_file)
        sys.exit(1)

    if os.path.exists(output_file) and os.path.getsize(output_file) == 0:
        print("\nWarning: No matching files were found to process.")
        os.remove(output_file)
        print(f"Removed empty output file: {output_file}")
    else:
        print(f"\nDone. Output successfully written to {output_file}")

def walk_and_process(outfile, input_dir, allowed_extensions, spec=None, use_gitignore=False):
    """
    Helper function to perform the directory walk and file processing.
    """
    for root, dirs, files in os.walk(input_dir, topdown=True):
        # In git-aware mode, explicitly and always ignore the .git directory.
        # This is a fundamental behavior of Git itself.
        if use_gitignore and '.git' in dirs:
            dirs.remove('.git')

        current_spec = spec
        if current_spec is None:
            # Determine the search boundary and filenames based on the mode
            if use_gitignore:
                # Search up to the .git root, or fall back to the input dir if not in a repo
                stop_dir = find_git_root(root) or input_dir
                ignore_filenames = ['.gitignore', '.dumpignore']
            else:
                # Default mode: only .dumpignore, stop at the input directory
                stop_dir = input_dir
                ignore_filenames = ['.dumpignore']
            
            patterns = find_and_load_ignore_files(stop_dir, root, ignore_filenames)
            current_spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

        # Filter directories and files
        dir_paths_to_check = [os.path.relpath(os.path.join(root, d), input_dir).replace("\\", "/") + '/' for d in dirs]
        ignored_dirs = set(current_spec.match_files(dir_paths_to_check))
        dirs[:] = [d for d, rel_d_path in zip(dirs, dir_paths_to_check) if rel_d_path not in ignored_dirs]

        for filename in files:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, input_dir).replace("\\", "/")
            
            if current_spec.match_file(rel_path):
                continue

            if allowed_extensions is not None:
                if not filename.lower().endswith(tuple(allowed_extensions)):
                    continue
            
            header_path = os.path.join(os.path.basename(input_dir), rel_path).replace("\\", "/")

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
                outfile.write(f"// Error reading file: {e}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Concatenates source files into a single output file, respecting hierarchical ignore files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input_dirs", nargs='+', help="One or more input directories to scan.")
    parser.add_argument("output_file", help="The base name for the output file.")
    parser.add_argument(
        "--ignore", dest="ignore_file", metavar="IGNORE_FILE",
        help="Path to a specific .gitignore-style file for exclusion.\nIf provided, this OVERRIDES all hierarchical searches."
    )
    parser.add_argument(
        "--use-gitignore",
        action="store_true",
        help="Enable Git compatibility mode.\nSearches for .gitignore and .dumpignore files up to the project's .git root.\nIf disabled (default), only searches for .dumpignore files up to the input directory."
    )
    parser.add_argument(
        "--exts", dest="exts_file", metavar="EXTS_FILE",
        help="Path to a file listing allowed file extensions.\nIf omitted, all extensions are included."
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    args = parser.parse_args()
    
    allowed_extensions = load_allowed_extensions(args.exts_file)

    collect_source_files(args.input_dirs, args.output_file, args.ignore_file, args.use_gitignore, allowed_extensions)

