from ollama import chat
from pathlib import Path
import subprocess
import platform
from memory import Memory

memory = Memory()

MODEL = "nemotron-3-super:cloud"

def ask_model(prompt):
    response = chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.message.content

def detect_request(request):
    """Detect user intent and return structured response from LLM"""
    prompt = f"""
<<<<<<< Updated upstream
You are a request classifier.
Determine the user's intent.
Return ONLY the structured output.

Possible actions:
CREATE - Create a single file
CREATE_FILES - Create multiple files
MODIFY - Modify an existing file
EXPLAIN - Explain a file
RUN - Run a file
RENAME - Rename a file
CREATE_FOLDER - Create a folder
ERROR - Unknown or invalid request

Return EXACTLY this format based on action type.

For CREATE:
ACTION: CREATE
=======
You are the Planner of a Coding Agent.

Your ONLY responsibility is to decide the NEXT action.

You NEVER generate code.
You NEVER explain code.
You NEVER execute code.

You ONLY decide what the next tool should be.

========================
CURRENT USER GOAL
========================

{request}

========================
CURRENT MEMORY
========================
>>>>>>> Stashed changes

For CREATE_FILES:
ACTION: CREATE_FILES

<<<<<<< Updated upstream
For MODIFY:
ACTION: MODIFY
FILE: <filename>
=======
Recent Files:
{chr(10).join(memory.recent_files) if memory.recent_files else "None"}
>>>>>>> Stashed changes

For EXPLAIN:
ACTION: EXPLAIN
FILE: <filename>

For RUN:
ACTION: RUN
FILE: <filename>

For RENAME:
ACTION: RENAME
FILE: <old_filename>
NEW_NAME: <new_filename>

For CREATE_FOLDER:
ACTION: CREATE_FOLDER
FOLDER: <folder_path>

For ERROR:
ACTION: ERROR

<<<<<<< Updated upstream
Rules:
- Return ONLY the structured output
- No markdown
- No explanations
- Use EXACT field names as shown

User Request:
{request}
=======
Fix Attempts:
{memory.fix_attempts}

Last Tool Success:
{memory.last_tool_success}

========================
AVAILABLE ACTIONS
========================

CREATE
MODIFY
EXPLAIN
RUN
FINISH
ERROR

========================
PLANNING RULES
========================

1. Read the user's goal carefully.

2. Decide ONLY the NEXT action.

3. Never generate code.

4. Never explain your reasoning.

5. Never invent filenames.

6. If the user explicitly asks to CREATE a program,
   return CREATE.

7. If the user explicitly asks to RUN a file,
   return RUN.

8. If the user explicitly asks to MODIFY, FIX, CHANGE or UPDATE a file,
   return MODIFY.

9. If the user explicitly asks to EXPLAIN a file,
   return EXPLAIN.

10. If the requested file already exists in Recent Files,
    NEVER return CREATE for that file.

11. After CREATE succeeds,
    the next action should be RUN for the created file.

12. If RUN fails and Last Error is not empty:

    - If Fix Attempts < 5
      return MODIFY.

    - Otherwise
      return FINISH.

13. After MODIFY,
    the next action should be RUN.

14. If the last action was RUN
    and Last Tool Success is True,
    return FINISH.

15. If the goal has already been completed,
    return FINISH.

16. If you cannot determine the correct action,
    return ERROR.

========================
OUTPUT FORMAT
========================

Return EXACTLY TWO lines.

ACTION: <ACTION>

FILE: <filename or empty>

Example:

ACTION: RUN
FILE: calculator.py

Do not return anything else.
Do not use markdown.
Do not use backticks.
Do not explain.
>>>>>>> Stashed changes
"""

    return ask_model(prompt)

def parse_response(response):
    """Parse LLM response into a dictionary of parameters"""
    params = {
        "action": "",
        "file": "",
        "folder": "",
        "new_name": ""
    }
    
    for line in response.splitlines():
        line = line.strip()
        
        if line.startswith("ACTION:"):
            params["action"] = line.replace("ACTION:", "").strip().upper()
        elif line.startswith("FILE:"):
            params["file"] = line.replace("FILE:", "").strip()
        elif line.startswith("FOLDER:"):
            params["folder"] = line.replace("FOLDER:", "").strip()
        elif line.startswith("NEW_NAME:"):
            params["new_name"] = line.replace("NEW_NAME:", "").strip()
    
    return params

def parse_code_response(response):
    """Parse code generation response to extract filename and code"""
    lines = response.splitlines()
    filename = ""
    code = []
    reading_code = False
    
    if "FILENAME:" not in response:
        return "", ""
    
    if "CODE:" not in response:
        return "", ""
    
    for line in lines:
        if line.startswith("FILENAME:"):
            filename = line.replace("FILENAME:", "").strip()
        elif line.startswith("CODE:"):
            reading_code = True
        elif reading_code:
            if line.strip().startswith("```"):
                continue
            code.append(line)
    
    return filename, "\n".join(code).strip()

def parse_files_response(response):
    """Parse multiple files from LLM response"""
    files = []
    current_file = None
    current_code = []
    
    lines = response.splitlines()
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("FILE:"):
            # Save previous file if exists
            if current_file is not None:
                files.append({
                    "filename": current_file,
                    "code": "\n".join(current_code).strip()
                })
            
            # Start new file
            current_file = line.replace("FILE:", "").strip()
            current_code = []
            
        elif line == "END_FILE":
            if current_file is not None:
                files.append({
                    "filename": current_file,
                    "code": "\n".join(current_code).strip()
                })
                current_file = None
                current_code = []
                
        elif current_file is not None and line.startswith("CODE:"):
            continue  # Skip CODE: line, start collecting after it
            
        elif current_file is not None:
            if not line.startswith("```"):  # Skip markdown markers
                current_code.append(line)
    
    # Handle last file if no END_FILE
    if current_file is not None:
        files.append({
            "filename": current_file,
            "code": "\n".join(current_code).strip()
        })
    
    return files

def generate_file(request):
    """Generate a single file using LLM"""
    prompt = f"""
You are a senior software engineer.

Generate ONE source code file for the user's request.

User Request:
{request}

Rules:
1. Choose a suitable filename.
2. Choose the correct extension.
3. Return exactly this format.

FILENAME: filename.extension

CODE:
<only the source code>

Do not use markdown.
Do not use triple backticks.
Do not explain anything.
"""
    
    answer = ask_model(prompt)
    return parse_code_response(answer)

def generate_files(request):
    """Generate multiple files using LLM"""
    prompt = f"""
You are a senior software engineer.

Generate MULTIPLE source code files for the user's request.

User Request:
{request}

Rules:
1. Return files in this exact format:

FILE: filename1.extension
CODE:
<source code>
END_FILE

FILE: filename2.extension
CODE:
<source code>
END_FILE

2. Include ALL necessary files for the project.
3. Do not use markdown.
4. Do not use triple backticks.
5. Do not explain anything.
6. Use EXACT format shown above.
"""
    
    answer = ask_model(prompt)
    return parse_files_response(answer)

def get_file_path(workspace_path, filename):
    file_path = (workspace_path / filename).resolve()
    
    if workspace_path.resolve() not in file_path.parents and file_path != workspace_path.resolve():
        raise ValueError("Access outside the workspace is not allowed.")
    
    return file_path

def save_file(workspace_path, filename, code):
    """Save code to file with workspace protection and overwrite check"""
    file_path = get_file_path(workspace_path, filename)
    
    if file_path.exists():
        while True:
            choice = input(
                f"'{filename}' already exists.\n"
                "Overwrite? (y/n): "
            ).strip().lower()
            
            if choice == "y":
                break
            elif choice == "n":
                print("File save cancelled.")
                return False
            else:
                print("Please enter y or n.")
    
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(code)
        print(f"File saved: {filename}")
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False

def create_file(workspace_path, request):
    """Create a single file"""
    filename, code = generate_file(request)
    
    if not filename:
        print("Model did not return a filename.")
        return
    
    if not code:
        print("Model did not return any code.")
        return
    
    print(f"\nCreated File: {filename}\n")
    print(code)
    
    if save_file(workspace_path, filename, code):
        print("File created successfully!")

def create_files(workspace_path, request):
    """Create multiple files for a project"""
    files = generate_files(request)
    
    if not files:
        print("Model did not return any files.")
        return
    
    print(f"\nGenerating {len(files)} files:\n")
    
    for file_info in files:
        filename = file_info["filename"]
        code = file_info["code"]
        
        if not filename or not code:
            print(f"Skipping invalid file entry: {file_info}")
            continue
        
        print(f"\n--- {filename} ---")
        print(code)
        print("-" * 40)
        
        save_file(workspace_path, filename, code)
    
    print("\nAll files created successfully!")

def explain_file(workspace_path, filename):
    file_path = get_file_path(workspace_path, filename)
    
    if not file_path.exists():
        print("File not found.")
        return
    
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()
    
    prompt = f"""
Explain the following code in simple language.

Code:

{code}
"""
    
    explanation = ask_model(prompt)
    
    print("\nExplanation:\n")
    print(explanation)

def modify_file(workspace_path, request, filename):
    file_path = get_file_path(workspace_path, filename)
    if not file_path.exists():
        print("File not found.")
        return
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()
    
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    with open(backup_path, "w", encoding="utf-8") as backup:
        backup.write(code)
    
    prompt = f"""
Modify the following code.

User Request:
{request}

Current Code:

{code}

Rules:
- Return only the updated source code.
- Do not explain.
- Do not use markdown.
- Do not use triple backticks.
"""
    
    new_code = ask_model(prompt)
    
    new_code = new_code.replace("```python", "")
    new_code = new_code.replace("```", "")
    new_code = new_code.strip()
    
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(new_code)
    print("File modified successfully!")
    print(f"Backup created: {backup_path.name}")

def create_folder(workspace_path, folder_name):
    """Create a folder with workspace protection"""
    try:
        folder_path = get_file_path(workspace_path, folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"Folder created: {folder_name}")
    except Exception as e:
        print(f"Error creating folder: {e}")

def rename_file(workspace_path, old_name, new_name):
    """Rename a file with workspace protection"""
    try:
        old_path = get_file_path(workspace_path, old_name)
        new_path = get_file_path(workspace_path, new_name)
        
        if not old_path.exists():
            print(f"File not found: {old_name}")
            return
        
        if new_path.exists():
            print(f"File already exists: {new_name}")
            return
        
        old_path.rename(new_path)
        print(f"Renamed: {old_name} -> {new_name}")
    except Exception as e:
        print(f"Error renaming file: {e}")

<<<<<<< Updated upstream
def run_file(workspace_path, filename):
    """Run a file based on its extension"""
    file_path = get_file_path(workspace_path, filename)
    
    if not file_path.exists():
        print(f"File not found: {filename}")
        return
    
    extension = file_path.suffix.lower()
    
    # Language detection and command mapping
    commands = {
        ".py": ["python", str(file_path)],
        ".js": ["node", str(file_path)],
        ".cpp": None,  # Will handle compilation separately
        ".java": None,  # Will handle compilation separately
    }
    
    try:
        if extension == ".cpp":
            # Compile and run C++
            executable = file_path.with_suffix("")
            if platform.system() == "Windows":
                executable = executable.with_suffix(".exe")
            
            print(f"Compiling {filename}...")
            compile_result = subprocess.run(
                ["g++", str(file_path), "-o", str(executable)],
                capture_output=True,
                text=True
=======
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "returncode": -1
        }


def get_file_path(workspace_path, filename):
    file_path = (workspace_path / filename).resolve() ## for folder & file path

    if workspace_path.resolve() not in file_path.parents and file_path != workspace_path.resolve(): ## requirement 3
        raise ValueError("Access outside the workspace is not allowed.") ## error handling for requirement 3

    return file_path

def execute_goal(workspace_path, request):

    memory.update(goal=request)
    memory.step_count = 0
    memory.fix_attempts = 0

    max_steps = 15

    while memory.step_count < max_steps:

        response = plan_next_action(
            memory.goal,
            memory
        )

        print("\n===== Planner Response =====")
        print(response)
        print("============================\n")

        action, filename = parse_action(response)

        if not filename and memory.recent_files:
            filename = memory.recent_files[-1]

        if action == "CREATE":
            result = create_file(workspace_path, request)

        elif action == "MODIFY":
            result = modify_file(
                workspace_path,
                request,
                filename
>>>>>>> Stashed changes
            )
            
            if compile_result.returncode != 0:
                print(f"Compilation failed:\n{compile_result.stderr}")
                return
            
            print(f"Running {filename}...")
            result = subprocess.run(
                [str(executable)],
                capture_output=True,
                text=True
            )
            
        elif extension == ".java":
            # Compile and run Java
            print(f"Compiling {filename}...")
            compile_result = subprocess.run(
                ["javac", str(file_path)],
                capture_output=True,
                text=True
            )
<<<<<<< Updated upstream
            
            if compile_result.returncode != 0:
                print(f"Compilation failed:\n{compile_result.stderr}")
                return
            
            class_name = file_path.stem
            print(f"Running {filename}...")
            result = subprocess.run(
                ["java", "-cp", str(file_path.parent), class_name],
                capture_output=True,
                text=True
            )
            
        else:
            # Run interpreted languages
            command = commands.get(extension)
            if not command:
                print(f"Unsupported file type: {extension}")
                return
            
            print(f"Running {filename}...")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )
        
        # Print output
        if result.stdout:
            print("\nOutput:")
            print(result.stdout)
        
        if result.stderr:
            print("\nErrors:")
            print(result.stderr)
            
        if result.returncode == 0:
            print(f"\n{filename} executed successfully!")
        else:
            print(f"\n{filename} exited with code: {result.returncode}")
            
    except FileNotFoundError as e:
        print(f"Required runtime not found: {e}")
    except Exception as e:
        print(f"Error running file: {e}")

def dispatch_action(params, workspace_path, request):
    """Route action to appropriate handler function"""
    TOOLS = {
        "CREATE": lambda: create_file(workspace_path, request),
        "CREATE_FILES": lambda: create_files(workspace_path, request),
        "MODIFY": lambda: modify_file(workspace_path, request, params["file"]),
        "EXPLAIN": lambda: explain_file(workspace_path, params["file"]),
        "RUN": lambda: run_file(workspace_path, params["file"]),
        "RENAME": lambda: rename_file(workspace_path, params["file"], params["new_name"]),
        "CREATE_FOLDER": lambda: create_folder(workspace_path, params["folder"]),
    }
    
    action = params.get("action", "ERROR")
    
    if action == "ERROR":
        print("Sorry, I don't understand your request.")
        return False
    
    handler = TOOLS.get(action)
    if handler:
        try:
            handler()
            return True
        except Exception as e:
            print(f"Error executing {action}: {e}")
            return False
    else:
        print(f"Unknown action: {action}")
        return False
=======

        elif action == "FINISH":
            print("Goal completed.")
            break

        else:
            print("Planner returned invalid action.")
            break

        memory.update(
            output=result["output"],
            error=result["error"],
            success=result["success"]
        )

        if result["success"]:
            memory.fix_attempts = 0

        if not result["success"]:

            memory.fix_attempts += 1

            memory.update(
                fix_attempt=f"Attempt {memory.fix_attempts}"
            )
    if memory.step_count >= max_steps:
        print("\nMaximum agent steps reached.")



>>>>>>> Stashed changes

def main():
    print("=== Simple Single Coding Agent ===")
    
    workspace = input("Enter workspace folder: ").strip()
    workspace_path = Path(workspace)
    
    if not workspace_path.exists():
        print("Workspace does not exist.")
        return
    
    if not workspace_path.is_dir():
        print("Workspace is not a folder.")
        return
    
    print(f"Workspace: {workspace_path}")
    
    while True:
        request = input("\nEnter your request: ")
        
        # New pipeline: detect → parse → dispatch
        response = detect_request(request)
        params = parse_response(response)
        
        print(f"Detected action: {params['action']}")
        
        dispatch_action(params, workspace_path, request)

if __name__ == "__main__":
    main()