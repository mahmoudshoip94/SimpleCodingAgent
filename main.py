from ollama import chat
from pathlib import Path
import subprocess
import sys
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

def detect_action(request):
    prompt = f"""
You are a request classifier.
Determine the user's intent.
Return ONLY two lines.

Possible actions:
CREATE
EXPLAIN
MODIFY
RUN
ERROR

Return EXACTLY this format.
ACTION: <ACTION>
FILE: <filename or empty>

Rules:
- CREATE -> FILE must be empty.
- EXPLAIN -> extract the filename.
- MODIFY -> extract the filename.
- RUN -> extract the filename.
- No markdown.
- No explanations.

User Request:
{request}
"""

    return ask_model(prompt)

def parse_action(response):
    action = ""
    filename = ""

    for line in response.splitlines():

        if line.startswith("ACTION:"):
            action = line.replace("ACTION:", "").strip().upper()

        elif line.startswith("FILE:"):
            filename = line.replace("FILE:", "").strip()

    return action, filename

def parse_response(response):
    lines = response.splitlines()
    filename = ""
    code = []
    reading_code = False
    if "FILENAME:" not in response:
        return "", ""

    if "CODE:" not in response:
        return "", ""

    for line in lines:

        if line.startswith("FILENAME:"): ## extract filename from the response
            filename = line.replace("FILENAME:", "").strip()

        elif line.startswith("CODE:"): ## start reading code after "CODE:" line
            reading_code = True

        elif reading_code: ## read code lines after "CODE:" line
            if line.strip().startswith("```"):
                continue

            code.append(line)

    return filename, "\n".join(code).strip()

def create_file(workspace_path, request):
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
    filename, code = parse_response(answer)
    if not filename: ## check if filename is returned
        print("Model did not return a filename.")
        return
    if not code: ## check if code is returned
        print("Model did not return any code.")
        return


    print(f"\nCreated File: {filename}\n")
    print(code)

    file_path = get_file_path(workspace_path, filename) ## create file path using workspace path and filename
    file_path = get_file_path(workspace_path, filename)## create file path using workspace path and filename

    if file_path.exists():
        while True:
            choice = input(
                f"'{filename}' already exists.\n"
                "Overwrite? (y/n): "
            ).strip().lower()

            if choice == "y":
                break

            elif choice == "n":
                print("File creation cancelled.")
                return

            else:
                print("Please enter y or n.")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(code)
    print("File created successfully!")

    memory.update(
    action="CREATE",
    files=[filename],
    folder=str(workspace_path)
)

def explain_file(workspace_path, filename):
    file_path = get_file_path(workspace_path, filename)## create & check file path using workspace path and filename

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

    memory.update(
    action="EXPLAIN",
    files=[filename]
)

def modify_file(workspace_path, request, filename):
    file_path = get_file_path(workspace_path, filename)
    if not file_path.exists():
        print("File not found.")
        return
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    backup_path = file_path.with_suffix(file_path.suffix + ".bak") ## file.py.bak
    with open(backup_path, "w", encoding="utf-8") as backup:  ## save backup of the original file
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

    new_code = new_code.replace("```python", "") ## remove any markdown formatting if present
    new_code = new_code.replace("```", "")
    new_code = new_code.strip()

    with open(file_path, "w", encoding="utf-8") as file: ## save the modified code to the original file
        file.write(new_code)
    print("File modified successfully!")
    print(f"Backup created: {backup_path.name}")

    memory.update(
    action="MODIFY",
    files=[filename]
)

def run_file(workspace_path, filename):
    file_path = get_file_path(workspace_path, filename)

    if not file_path.exists():
        print("File not found.")
        return

    suffix = file_path.suffix.lower()

    try:

        if suffix == ".py":
            result = subprocess.run(
                [sys.executable, file_path.name],
                cwd=file_path.parent,
                capture_output=True,
                text=True
            )

        elif suffix == ".js":
            result = subprocess.run(
                ["node", file_path.name],
                cwd=file_path.parent,
                capture_output=True,
                text=True
            )

        elif suffix == ".cpp":

            exe_name = file_path.stem + ".exe"

            compile_result = subprocess.run(
                ["g++", file_path.name, "-o", exe_name],
                cwd=file_path.parent,
                capture_output=True,
                text=True
            )

            if compile_result.returncode != 0:
                print("Compilation failed.\n")
                print(compile_result.stderr)
                return

            result = subprocess.run(
                [exe_name],
                cwd=file_path.parent,
                capture_output=True,
                text=True
            )

        elif suffix == ".java":

            compile_result = subprocess.run(
                ["javac", file_path.name],
                cwd=file_path.parent,
                capture_output=True,
                text=True
            )

            if compile_result.returncode != 0:
                print("Compilation failed.\n")
                print(compile_result.stderr)
                return

            result = subprocess.run(
                ["java", file_path.stem],
                cwd=file_path.parent,
                capture_output=True,
                text=True
            )

        else:
            print(f"Unsupported file type: {suffix}")
            return

        if result.stdout:
            print("\nOutput:\n")
            print(result.stdout)

        if result.stderr:
            print("\nErrors:\n")
            print(result.stderr)

        if result.returncode == 0:
            print("Program executed successfully!")

            memory.update(
                action="RUN",
                files=[filename]
            )

        else:
            print(f"Program exited with code {result.returncode}")       

    except FileNotFoundError as e:
        print(f"Required tool is not installed: {e.filename}")

    except Exception as e:
        print(f"Execution failed: {e}")

def get_file_path(workspace_path, filename):
    file_path = (workspace_path / filename).resolve() ## for folder & file path

    if workspace_path.resolve() not in file_path.parents and file_path != workspace_path.resolve(): ## requirement 3
        raise ValueError("Access outside the workspace is not allowed.") ## error handling for requirement 3

    return file_path

def main():
    print("=== Simple Single Coding Agent ===")

    workspace = input("Enter workspace folder: ").strip() ## requirment 2
    workspace_path = Path(workspace)
    if not workspace_path.exists():
        print("Workspace does not exist.")
        return
    if not workspace_path.is_dir():
        print("Workspace is not a folder.")
        return
    print(f"Workspace: {workspace_path}")


    while True:
        request = input("Enter your request: ")

        response = detect_action(request)

        action, filename = parse_action(response)

        # لو الموديل مرجعش اسم ملف استخدم آخر ملف
        if not filename and memory.recent_files:
            filename = memory.recent_files[-1]

        if action not in ["CREATE", "EXPLAIN", "MODIFY", "RUN"]:
            print("Sorry, I don't understand your request.")
            continue
        elif action == "CREATE":
            create_file(workspace_path, request)
        elif action == "EXPLAIN":
            explain_file(workspace_path, filename)
        elif action == "MODIFY":
            modify_file(workspace_path, request, filename)
        elif action == "RUN":
            run_file(workspace_path, filename)

if __name__ == "__main__":
    main()