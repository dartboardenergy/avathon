#!/usr/bin/env python3
"""
Test runner for all Avathon toolset phases.
Runs tests in order: Client → Parser → Toolset
"""

import subprocess
import sys

def run_test(script_name, phase_name):
    """Run a test script and return success status."""
    print(f"\n{'='*60}")
    print(f"🧪 Running {phase_name}")
    print(f"{'='*60}")
    
    try:
        # Run from parent directory to maintain imports  
        result = subprocess.run([sys.executable, f"tests/{script_name}"], 
                              cwd="../", capture_output=True, text=True, timeout=60)
        
        # Show output
        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {phase_name} PASSED")
            return True
        else:
            print(f"❌ {phase_name} FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {phase_name} TIMEOUT (60s)")
        return False
    except Exception as e:
        print(f"💥 {phase_name} ERROR: {e}")
        return False

def main():
    """Run all tests in sequence."""
    print("🚀 Avathon Toolset Test Suite")
    
    tests = [
        ("test_client.py", "Phase 1: API Client"),
        ("test_parser.py", "Phase 2: OpenAPI Parser"), 
        ("test_toolset.py", "Phase 3: Core Toolset")
    ]
    
    passed = 0
    failed = 0
    
    for script, phase in tests:
        if run_test(script, phase):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {passed}/{len(tests)} ({passed/len(tests)*100:.1f}%)")
    
    if failed == 0:
        print(f"\n🎉 ALL TESTS PASSED! Toolset is ready for integration.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()