# **AI Source Dump Tool (dump.py) \- Usage Guide**

## **1\. Overview**

The AI Source Dump Tool is a powerful command-line utility designed to intelligently scan one or more directories and concatenate all relevant source code and text files into a single, well-formatted output file that can be passed to an AI for analysis. Each file's content is preceded by a clear header indicating its original path.

Its primary purpose is to create a "snapshot" of a project's source code that can be easily shared, reviewed, or fed into other systems (like language models) without including unnecessary files like build artifacts, temporary files, or local configuration.

## **2\. Core Concepts: How Ignoring Works**

The script's power comes from its flexible file exclusion mechanism, which operates in three distinct modes.

### **Mode 1: Default (.dumpignore only)**

If you run the script without any special flags, it will look for files named .dumpignore.

* **Hierarchical Search:** It searches for .dumpignore files in the current directory it's scanning and every parent directory up to the *input directory* you specified on the command line.  
* **Purpose:** This mode is perfect for creating dumps that are independent of your version control system. You can define dump-specific rules without altering your project's .gitignore.

### **Mode 2: Git Compatibility (\--use-gitignore)**

This is the most powerful mode for developers. When you add the \--use-gitignore flag, the script intelligently mimics Git's ignore behavior.

* **Git Root Awareness:** It searches upwards from the directory being scanned to find the project's root (the directory containing the .git folder). This becomes the boundary for its upward search for ignore files.  
* **Dual File System:** It reads ignore patterns from **both** .gitignore and .dumpignore files.  
* **Precedence:** Rules are applied in a specific order: .gitignore rules are applied first, and .dumpignore rules are applied last. This allows you to use your project's main .gitignore as a baseline and then add extra, dump-specific exclusions in .dumpignore to further refine the output.

### **Mode 3: Manual Override (\--ignore \<file\>)**

If you provide a specific file path using the \--ignore argument, the script will **only** use the rules from that single file. All automatic, hierarchical searches for .gitignore or .dumpignore are disabled.

## **3\. Command-Line Usage**

### **Syntax**

python dump.py \<input\_dirs ...\> \<output\_file\> \[options\]

### **Arguments**

* **input\_dirs** (Required): One or more space-separated paths to the directories you want to scan.  
* **output\_file** (Required): The base name for the output text file. If the file already exists, a number will be appended to create a unique name (e.g., my\_dump\_1.txt).

### **Options**

* **\--use-gitignore**: (Flag) Activates Git Compatibility Mode, searching for both .gitignore and .dumpignore files up to the Git project root.  
* **\--ignore \<IGNORE\_FILE\>**: Overrides all automatic searching and uses only the specified ignore file.  
* **\--exts \<EXTS\_FILE\>**: Path to a file containing a list of allowed file extensions (one per line, e.g., .py, .html). If omitted, all files not ignored will be included.

## **4\. Practical Examples**

### **Example 1: Basic Dump of a Project**

Dump the contents of the MyWebApp and SharedLibrary directories into project\_dump.txt, using only the .dumpignore files found within them.

python dump.py ./MyWebApp ./SharedLibrary project\_dump

### **Example 2: Git-Aware Dump**

Dump an entire Git repository from its root directory. This will respect all .gitignore files and can be further refined with .dumpignore files.

python dump.py . my\_repo\_dump \--use-gitignore

### **Example 3: Dumping Only Specific File Types**

Dump only Python and Markdown files from the current project, respecting the Git ignore rules.

First, create a file named allowed\_exts.txt:

.py  
.md  
.txt

Then, run the command:

python dump.py . my_python\_dump --use-gitignore --exts allowed_exts.txt

### **Example 4: Advanced Dump from a Subdirectory**

You are inside the src/components directory of a large project. You want to dump only this component's folder, but still respect the root-level .gitignore and any other ignore files on the way up to the project root.

\# Assuming you are in the 'src/components' directory  
python dump.py . component_dump --use-gitignore

The script will correctly find the .git root several levels up and apply all relevant ignore files.

## **5\. Setting Up Your Ignore Files**

You can use standard .gitignore syntax in both file types.

#### **.gitignore (Example)**

This file excludes common development artifacts.

```
# IDE and OS files  
.vscode/  
.idea/  
*.suo  
*.user  
Thumbs.db

# Build output  
bin/  
obj/  
dist/

# Dependencies  
node\_modules/  
packages/

# Log files  
*.log
```

#### **.dumpignore (Example)**

This file adds extra rules just for dumping. It will be applied *after* the .gitignore rules when in Git-aware mode.

```
# Exclude test data and large assets from the dump  
tests/testdata/  
assets/videos/

# Don't include markdown documentation in the dump  
*.md

# But DO include the main README.md (negation)  
!README.md
```

In this scenario, \*.log files (ignored by git) and \*.md files (ignored by dump) would both be excluded from the final output, except for README.md.


6. Example Output Structure
   To understand what the final output looks like, consider the following simple project structure:
```
   MyProject/
   ├── .gitignore
   ├── README.md
   └── src/
    ├── main.py
    └── utils/
        └── helpers.py
```
If you run the command python dump.py ./MyProject project_dump --use-gitignore, the generated project_dump.txt file will have the following structure:

```
//================================================================================
// File: MyProject/README.md
//================================================================================

This is the main README file for MyProject.


//================================================================================
// File: MyProject/src/main.py
//================================================================================

from utils import helpers

def main():
    print("Hello from main!")
    helpers.do_something()

if __name__ == "__main__":
    main()


//================================================================================
// File: MyProject/src/utils/helpers.py
//================================================================================

def do_something():
    print("The helper function was called.")

```

As you can see, each file's content is clearly separated by a header that shows its full relative path within the input directory.
