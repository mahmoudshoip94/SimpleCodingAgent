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

def plan_next_action(request, memory):
    prompt = f"""
You are the planner of a coding agent.

Your job is NOT to solve the user's request.
Your job is ONLY to decide the next action that should be executed.

Current User Goal:
{request}

Current Memory:

Last Action:
{memory.last_action}

Recent Files:
{memory.recent_files}

Last Folder:
{memory.last_folder}

Last Output:
{memory.last_output}

Last Error:
{memory.last_error}

Last Fix Attempt:
{memory.last_fix_attempt}

Rules:
- Return ONLY two lines.
- No markdown.
- No explanations.

- CREATE -> create a new source file.
- MODIFY -> modify an existing file.
- EXPLAIN -> explain an existing file.
- RUN -> execute the current file.

- If the last action was RUN and Last Error is NOT empty,
  your next action MUST be MODIFY for the same file.

- If the last action was MODIFY and there is no error,
  your next action should be RUN.

- If everything completed successfully,
  return FINISH.

- If you cannot determine the next action,
  return ERROR.

Return EXACTLY this format:

ACTION: <ACTION>
FILE: <filename or empty>
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
    try:
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
            return {
        "success": False,
        "output": "",
        "error": "Model did not return filename"
    }
        if not code: ## check if code is returned
            print("Model did not return any code.")
            return {
        "success": False,
        "output": "",
        "error": "Model did not return code"
    }


        print(f"\nCreated File: {filename}\n")
        print(code)

        file_path = get_file_path(workspace_path, filename) ## create file path using workspace path and filename

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
        return {
        "success": True,
        "output": f"Created {filename}",
        "error": None
    }
    except Exception as e:
        print(e)

        return {
            "success": False,
            "output": "",
            "error": str(e)
        }

def explain_file(workspace_path, filename):
    file_path = get_file_path(workspace_path, filename)## create & check file path using workspace path and filename

    if not file_path.exists():
        print("File not found.")

        return {
            "success": False,
            "output": "",
            "error": "File not found"
        }

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
    return {
    "success": True,
    "output": explanation,
    "error": None
}

def modify_file(workspace_path, request, filename):
    file_path = get_file_path(workspace_path, filename)
    if not file_path.exists():
        print("File not found.")
        return {
            "success": False,
            "output": "",
            "error": "File not found"
        }
    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    backup_path = file_path.with_suffix(file_path.suffix + ".bak") ## file.py.bak
    with open(backup_path, "w", encoding="utf-8") as backup:  ## save backup of the original file
        backup.write(code)

    prompt = f"""
You are fixing an existing source code.

Original User Goal:
{memory.goal}

Last Execution Error:
{memory.last_error}

User Request:
{request}

Current Code:

{code}

Rules:
- Fix ONLY the reported error.
- Preserve the original functionality.
- Return only the updated source code.
- No markdown.
- No explanations.
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
    return {
    "success": True,
    "output": f"Modified {filename}",
    "error": None
}

#==================================================================
def run_python(file_path):
    result = subprocess.run(
        [sys.executable, file_path.name],
        cwd=file_path.parent,
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr,
        "returncode": result.returncode
    }
def run_javascript(file_path):
    result = subprocess.run(
        ["node", file_path.name],
        cwd=file_path.parent,
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr,
        "returncode": result.returncode
    }
def run_cpp(file_path):

    exe_name = file_path.stem + ".exe"

    compile_result = subprocess.run(
        ["g++", file_path.name, "-o", exe_name],
        cwd=file_path.parent,
        capture_output=True,
        text=True
    )

    if compile_result.returncode != 0:
        return {
            "success": False,
            "output": "",
            "error": compile_result.stderr,
            "returncode": compile_result.returncode
        }

    result = subprocess.run(
        [exe_name],
        cwd=file_path.parent,
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr,
        "returncode": result.returncode
    }
def run_java(file_path):

    compile_result = subprocess.run(
        ["javac", file_path.name],
        cwd=file_path.parent,
        capture_output=True,
        text=True
    )

    if compile_result.returncode != 0:
        return {
            "success": False,
            "output": "",
            "error": compile_result.stderr,
            "returncode": compile_result.returncode
        }

    result = subprocess.run(
        ["java", file_path.stem],
        cwd=file_path.parent,
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr,
        "returncode": result.returncode
    }

RUNNERS = {
    ".py": run_python,
    ".js": run_javascript,
    ".cpp": run_cpp,
    ".java": run_java
}
#=================================================================
def run_file(workspace_path, filename):

    file_path = get_file_path(workspace_path, filename)

    if not file_path.exists():
        print("File not found.")

        return {
            "success": False,
            "output": "",
            "error": "File not found",
            "returncode": -1
        }

    suffix = file_path.suffix.lower()

    runner = RUNNERS.get(suffix)

    if runner is None:

        print(f"Unsupported file type: {suffix}")

        return {
            "success": False,
            "output": "",
            "error": f"Unsupported file type: {suffix}",
            "returncode": -1
        }

    try:

        result = runner(file_path)

        if result["output"]:
            print("\nOutput:\n")
            print(result["output"])

        if result["error"]:
            print("\nErrors:\n")
            print(result["error"])

        if result["success"]:

            print("Program executed successfully!")

            memory.update(
                action="RUN",
                files=[filename],
                output=result["output"]
            )

        else:

            print(f"Program exited with code {result['returncode']}")

            memory.update(
                action="RUN",
                files=[filename],
                output=result["output"],
                error=result["error"]
            )

        return result

    except FileNotFoundError as e:

        print(f"Required tool is not installed: {e.filename}")

        return {
            "success": False,
            "output": "",
            "error": str(e),
            "returncode": -1
        }

    except Exception as e:

        print(f"Execution failed: {e}")

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
    max_fix_attempts = 5
    fix_attempts = 0

    while True:

        response = plan_next_action(
            memory.goal,
            memory
        )

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
            )

        elif action == "EXPLAIN":
            result = explain_file(
                workspace_path,
                filename
            )

        elif action == "RUN":
            result = run_file(
                workspace_path,
                filename
            )

        else:
            print("Planner returned invalid action.")
            break

        memory.update(
            output=result["output"],
            error=result["error"]
        )

        if result["success"]:
            break

        if action == "RUN" and not result["success"]:
            fix_attempts += 1

            memory.update(
                fix_attempt=f"Attempt {fix_attempts}"
            )

            print(f"\n=== Auto Fix Attempt {fix_attempts}/{max_fix_attempts} ===")

            if fix_attempts >= max_fix_attempts:
                print("\nMaximum fix attempts reached.")
                break

            continue



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
        request = input("\nEnter your request: ").strip()

        if not request:
            continue

        execute_goal(workspace_path, request)

if __name__ == "__main__":
    main()