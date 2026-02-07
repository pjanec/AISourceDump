# 1. enable auto-save in  google ai studio cat so it gets saved to goodle disk
# 2. in google disk, download the file as json
# 3. use this utility to extract the conversion to a separate file

import json
import os
import sys

# --- CONFIGURATION ---
# Base length for the separator lines
SEPARATOR_LENGTH = 60
SKIP_THOUGHTS = True

def extract_text_from_json(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'chunkedPrompt' not in data or 'chunks' not in data['chunkedPrompt']:
            print("Error: JSON structure does not match expected AI Studio format (missing 'chunkedPrompt').")
            return

        chunks = data['chunkedPrompt']['chunks']
        
        with open(output_path, 'w', encoding='utf-8') as out:
            count = 0
            
            for chunk in chunks:
                # Get role (usually 'user' or 'model')
                role = chunk.get('role', 'unknown').lower()
                text = chunk.get('text', '')
                is_thought = chunk.get('isThought', False)

                # Handle 'parts' list if top-level text is empty
                if not text and 'parts' in chunk:
                    parts_text = []
                    for part in chunk['parts']:
                        if 'text' in part:
                            parts_text.append(part['text'])
                    text = "".join(parts_text)
                
                # Skip empty chunks
                if not text:
                    continue

                # Skip thoughts if configured
                if is_thought and SKIP_THOUGHTS:
                    continue

                # Prepare the label for the separator
                label = role
                if is_thought:
                    label = f"{role} (thought)"

                # Build the dynamic separator: "--- user --------------------"
                # 4 chars for initial "--- ", then label, then space, then fill remaining with "-"
                dash_count = max(5, SEPARATOR_LENGTH - len(label) - 5)
                separator = f"--- {label} " + ("-" * dash_count)

                # Write to file
                out.write(f"{separator}\n")
                out.write(text.strip())
                out.write("\n\n")
                
                count += 1

        print(f"Successfully extracted {count} messages to '{output_path}'.")

    except json.JSONDecodeError:
        print("Error: Failed to decode JSON. Please check if the file is valid.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_chat.py <input_json_file> <output_text_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    extract_text_from_json(input_file, output_file)
