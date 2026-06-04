# from the dumped TXT file extracts just the file paths from the headers separating individual files from each other
import sys
import re

def extract_paths(in_stream, out_stream):
    # Matches lines starting with "// File:" and captures everything after it
    pattern = re.compile(r"^\s*//\s*File:\s*(.+)$")
    
    for line in in_stream:
        match = pattern.match(line)
        if match:
            # Extract the path and strip any trailing whitespace/newlines
            file_path = match.group(1).strip()
            out_stream.write(file_path + '\n')

def main():
    in_stream = sys.stdin
    out_stream = sys.stdout

    # Override stdin if arg1 (input file) is provided
    if len(sys.argv) > 1:
        try:
            in_stream = open(sys.argv[1], 'r', encoding='utf-8')
        except IOError as e:
            sys.stderr.write(f"Error reading input file: {e}\n")
            sys.exit(1)

    # Override stdout if arg2 (output file) is provided
    if len(sys.argv) > 2:
        try:
            out_stream = open(sys.argv[2], 'w', encoding='utf-8')
        except IOError as e:
            sys.stderr.write(f"Error writing to output file: {e}\n")
            if in_stream is not sys.stdin:
                in_stream.close()
            sys.exit(1)

    try:
        extract_paths(in_stream, out_stream)
    finally:
        # Safely close files if we opened them
        if in_stream is not sys.stdin:
            in_stream.close()
        if out_stream is not sys.stdout:
            out_stream.close()

if __name__ == "__main__":
    main()