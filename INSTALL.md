## **Prerequisites & Setup**

Before using the script, you need to have Python installed on your system and install one third-party library. Using a virtual environment is highly recommended to keep your project dependencies isolated.

### **Step 1: Ensure Python is Installed**

This script requires Python 3.6 or newer. You can check your version by opening a terminal or command prompt and running:

python \--version

### **Step 2: Create a Virtual Environment (Recommended)**

Navigate to your project directory where you've saved `src_dump.py` and run the following command to create a virtual environment named `venv`:

python \-m venv venv

### **Step 3: Activate the Virtual Environment**

**On Windows:**  
.\\venv\\Scripts\\activate

* 

**On macOS/Linux:**  
source venv/bin/activate

* 

Your command prompt should now be prefixed with `(venv)`.

### **Step 4: Install the Required Library**

The script depends on the `pathspec` library to handle `.gitignore`\-style patterns. Install it using pip:

pip install pathspec

You are now ready to use the script.