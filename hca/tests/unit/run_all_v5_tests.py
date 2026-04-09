import os
import subprocess

def run_tests():
    test_files = [
        "tests/unit/test_foundation_v5.py",
        "tests/unit/test_approvals_v5.py",
        "tests/unit/test_runtime_replay_v5.py",
        "tests/unit/test_memory_v5.py",
        "tests/unit/test_meta_workspace_v5.py",
        "tests/unit/test_modules_api_v5.py"
    ]
    
    all_passed = True
    for test_file in test_files:
        print(f"Running {test_file}...")
        result = subprocess.run(["python3", test_file], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{test_file} passed")
        else:
            print(f"{test_file} failed")
            print(result.stdout)
            print(result.stderr)
            all_passed = False
            
    if all_passed:
        print("\nAll v5 tests passed!")
    else:
        print("\nSome v5 tests failed.")
        exit(1)

if __name__ == "__main__":
    run_tests()
