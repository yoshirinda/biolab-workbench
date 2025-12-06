import json
from app.core.project_manager import list_projects

def run_test():
    print("--- Running Project Listing Test ---")
    try:
        project_tree = list_projects()
        print("--- Result ---")
        print(json.dumps(project_tree, indent=2))
    except Exception as e:
        print(f"--- ERROR ---")
        import traceback
        traceback.print_exc()
    print("--- Test Finished ---")

if __name__ == "__main__":
    run_test()
