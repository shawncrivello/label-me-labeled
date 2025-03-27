#!/usr/bin/env python3
"""
Pre-check script for Legal Drive Labels Manager.

This script verifies that your environment is properly set up
to run the Legal Drive Labels Manager tool.
"""

import os
import sys
import importlib
import platform
import subprocess
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union


# Define required components
REQUIRED_PACKAGES = [
    ("google-api-python-client", "2.0.0"),
    ("google-auth-httplib2", "0.1.0"),
    ("google-auth-oauthlib", "0.4.0"),
]

OPTIONAL_PACKAGES = [
    ("pandas", "1.0.0"),
    ("matplotlib", "3.0.0"),
    ("seaborn", "0.11.0"),
]

# Define potential credential paths based on platform
CREDENTIAL_PATHS = [
    Path("credentials.json"),
    Path.home() / ".config" / "drive_labels" / "credentials.json",
]
if platform.system() == "Windows":
    CREDENTIAL_PATHS.append(Path(os.environ.get("APPDATA", "")) / "drive_labels" / "credentials.json")
elif platform.system() == "Darwin":  # macOS
    CREDENTIAL_PATHS.append(Path.home() / "Library" / "Application Support" / "drive_labels" / "credentials.json")


def check_python_version() -> Tuple[bool, str]:
    """
    Check if Python version is sufficient.
    
    Returns:
        Tuple of (success, message)
    """
    current = sys.version_info
    required = (3, 7)
    
    if current.major > required[0] or (current.major == required[0] and current.minor >= required[1]):
        return True, f"Python {current.major}.{current.minor}.{current.micro} detected (✓ meets minimum requirement: 3.7)"
    else:
        return False, f"Python {current.major}.{current.minor}.{current.micro} detected (✗ below minimum requirement: 3.7)"


def check_packages(packages: List[Tuple[str, str]]) -> List[Tuple[bool, str]]:
    """
    Check if required packages are installed with minimum versions.
    
    Args:
        packages: List of (package_name, min_version)
        
    Returns:
        List of (success, message) for each package
    """
    results = []
    
    for package_name, min_version in packages:
        try:
            # Try to import the package - will fail if not installed
            pkg = importlib.import_module(package_name)
            
            # Get version (different packages store it differently)
            version = "unknown"
            for attr in ["__version__", "version", "VERSION"]:
                if hasattr(pkg, attr):
                    version = getattr(pkg, attr)
                    break
            
            # Check if version is sufficient
            try:
                pkg_version = parse_version(version)
                min_pkg_version = parse_version(min_version)
                
                if pkg_version >= min_pkg_version:
                    results.append((True, f"{package_name} {version} installed (✓ meets minimum: {min_version})"))
                else:
                    results.append((False, f"{package_name} {version} installed (✗ below minimum: {min_version})"))
            except Exception:
                # If we can't parse the version, just report it's installed
                results.append((True, f"{package_name} installed (version undetectable, required: {min_version})"))
                
        except ImportError:
            results.append((False, f"{package_name} not found (✗ required: {min_version})"))
        except Exception as e:
            results.append((False, f"{package_name} error: {str(e)} (✗ required: {min_version})"))
    
    return results


def parse_version(version_str: Union[str, Tuple, List, Any]) -> Tuple[int, ...]:
    """
    Parse version string into comparable tuple.
    
    Args:
        version_str: Version string (e.g., "1.2.3") or other version representation
        
    Returns:
        Tuple of version components
    """
    # Handle non-string versions (like tuples)
    if not isinstance(version_str, str):
        if isinstance(version_str, tuple) or isinstance(version_str, list):
            return tuple(int(x) if isinstance(x, (int, str)) and str(x).isdigit() else 0 
                        for x in version_str)
        return (0,)
        
    # Extract digits only
    parts = []
    for part in version_str.split('.'):
        # Extract leading digits
        digits = ''
        for char in part:
            if char.isdigit():
                digits += char
            else:
                break
        
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    
    if not parts:
        return (0,)
    
    return tuple(parts)


def check_credentials() -> Tuple[bool, str]:
    """
    Check if Google API credentials are available.
    
    Returns:
        Tuple of (success, message)
    """
    for path in CREDENTIAL_PATHS:
        if path.exists():
            try:
                # Verify it's a valid credentials file (basic check)
                with open(path, 'r') as f:
                    content = f.read()
                    if '"client_id"' in content and '"client_secret"' in content:
                        return True, f"Credentials found at: {path}"
                    else:
                        return False, f"Found credentials file at {path} but it may be invalid (missing client_id or client_secret)"
            except Exception as e:
                return False, f"Found credentials file at {path} but couldn't read it: {str(e)}"
    
    # No credentials found
    return False, "Google API credentials not found. Please download OAuth credentials (credentials.json)"


def check_config_dir() -> Tuple[bool, str]:
    """
    Check if config directory exists or can be created.
    
    Returns:
        Tuple of (success, message)
    """
    # Determine config directory path based on platform
    if platform.system() == "Windows":
        config_dir = Path(os.environ.get("APPDATA", "")) / "drive_labels"
    elif platform.system() == "Darwin":  # macOS
        config_dir = Path.home() / "Library" / "Application Support" / "drive_labels"
    else:  # Linux/Unix
        config_dir = Path.home() / ".config" / "drive_labels"
    
    # Check if it exists
    if config_dir.exists():
        if os.access(config_dir, os.W_OK):
            return True, f"Config directory exists and is writable: {config_dir}"
        else:
            return False, f"Config directory exists but is not writable: {config_dir}"
    
    # Try to create it
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        return True, f"Config directory created: {config_dir}"
    except Exception as e:
        return False, f"Failed to create config directory at {config_dir}: {e}"


def check_install_status() -> Tuple[bool, str]:
    """
    Check if the package is properly installed.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        import legal_drive_labels_manager
        try:
            version = getattr(legal_drive_labels_manager, "__version__", "unknown")
            return True, f"Legal Drive Labels Manager installed (version: {version})"
        except AttributeError:
            return True, "Legal Drive Labels Manager installed (version not detected)"
    except ImportError:
        # Check if we're running from the source directory
        if Path("legal_drive_labels_manager").is_dir():
            return True, "Running from source directory (not installed as package)"
        return False, "Legal Drive Labels Manager package not found in Python path"


def check_authentication_test() -> Tuple[bool, str]:
    """
    Perform a simple authentication test without requiring real credentials.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        # Import without authenticating
        from legal_drive_labels_manager.auth.credentials import AuthManager
        
        # Create test instance without authenticating
        auth_manager = AuthManager()
        
        # Just check that the class is properly initialized
        if hasattr(auth_manager, 'authenticate') and callable(getattr(auth_manager, 'authenticate')):
            return True, "Authentication module successfully imported"
        else:
            return False, "Authentication module structure appears invalid"
    except ImportError:
        return False, "Could not import authentication module"
    except Exception as e:
        return False, f"Error testing authentication module: {str(e)}"


def run_all_checks() -> Dict[str, Dict[str, Any]]:
    """
    Run all pre-check tests.
    
    Returns:
        Dictionary with test results
    """
    results = {
        "python_version": {"result": None, "message": ""},
        "required_packages": {"result": None, "details": []},
        "optional_packages": {"result": None, "details": []},
        "credentials": {"result": None, "message": ""},
        "config_dir": {"result": None, "message": ""},
        "install_status": {"result": None, "message": ""},
        "auth_module": {"result": None, "message": ""},
        "overall": {"result": None, "message": ""}
    }
    
    # Check Python version
    results["python_version"]["result"], results["python_version"]["message"] = check_python_version()
    
    # Check required packages
    pkg_results = check_packages(REQUIRED_PACKAGES)
    results["required_packages"]["details"] = pkg_results
    results["required_packages"]["result"] = all(result for result, _ in pkg_results)
    
    # Check optional packages
    opt_pkg_results = check_packages(OPTIONAL_PACKAGES)
    results["optional_packages"]["details"] = opt_pkg_results
    results["optional_packages"]["result"] = all(result for result, _ in opt_pkg_results)
    
    # Check credentials
    results["credentials"]["result"], results["credentials"]["message"] = check_credentials()
    
    # Check config directory
    results["config_dir"]["result"], results["config_dir"]["message"] = check_config_dir()
    
    # Check installation status
    results["install_status"]["result"], results["install_status"]["message"] = check_install_status()
    
    # Check auth module if installed
    if results["install_status"]["result"]:
        results["auth_module"]["result"], results["auth_module"]["message"] = check_authentication_test()
    else:
        results["auth_module"]["result"] = False
        results["auth_module"]["message"] = "Cannot test authentication module (package not installed)"
    
    # Determine overall status
    critical_checks = ["python_version", "required_packages", "config_dir"]
    critical_results = [results[check]["result"] for check in critical_checks]
    
    results["overall"]["result"] = all(critical_results)
    if results["overall"]["result"]:
        results["overall"]["message"] = "Environment is correctly set up for Legal Drive Labels Manager!"
    else:
        results["overall"]["message"] = "Environment setup has issues that need to be addressed."
    
    return results


def fix_common_issues(results: Dict[str, Dict[str, Any]]) -> None:
    """
    Try to fix common issues based on check results.
    
    Args:
        results: Results from run_all_checks
    """
    if not results["required_packages"]["result"]:
        print("\nAttempting to install missing required packages...")
        for passed, message in results["required_packages"]["details"]:
            if not passed:
                package_name = message.split()[0]
                min_version = message.split("required: ")[1].rstrip(")")
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", 
                        f"{package_name}>={min_version}"
                    ])
                    print(f"Installed {package_name}")
                except subprocess.CalledProcessError:
                    print(f"Failed to install {package_name}")
    
    if not results["optional_packages"]["result"] and results["overall"]["result"]:
        print("\nWould you like to install optional packages for visualization? (y/n)")
        response = input().lower()
        if response.startswith('y'):
            print("Installing optional packages...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install",
                    "pandas>=1.0.0", "matplotlib>=3.0.0", "seaborn>=0.11.0"
                ])
                print("Optional packages installed successfully")
            except subprocess.CalledProcessError:
                print("Failed to install optional packages")
    
    # Try to create config directory if needed
    if not results["config_dir"]["result"]:
        print("\nAttempting to create config directory...")
        try:
            if platform.system() == "Windows":
                config_dir = Path(os.environ.get("APPDATA", "")) / "drive_labels"
            elif platform.system() == "Darwin":  # macOS
                config_dir = Path.home() / "Library" / "Application Support" / "drive_labels"
            else:  # Linux/Unix
                config_dir = Path.home() / ".config" / "drive_labels"
                
            config_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created config directory: {config_dir}")
        except Exception as e:
            print(f"Failed to create config directory: {e}")


def print_results(results: Dict[str, Dict[str, Any]]) -> None:
    """
    Print check results in a readable format.
    
    Args:
        results: Results from run_all_checks
    """
    print("\n" + "=" * 80)
    print("LEGAL DRIVE LABELS MANAGER - ENVIRONMENT CHECK")
    print("=" * 80 + "\n")
    
    # Python version
    print(f"Python Version: {results['python_version']['message']}")
    
    # Required packages
    print("\nRequired Packages:")
    for passed, message in results["required_packages"]["details"]:
        status = "✓" if passed else "✗"
        print(f"  [{status}] {message}")
    
    # Optional packages
    print("\nOptional Packages (for visualization):")
    for passed, message in results["optional_packages"]["details"]:
        status = "✓" if passed else "✗"
        print(f"  [{status}] {message}")
    
    # Credentials
    cred_status = "✓" if results["credentials"]["result"] else "✗"
    print(f"\nCredentials: [{cred_status}] {results['credentials']['message']}")
    
    # Config directory
    config_status = "✓" if results["config_dir"]["result"] else "✗"
    print(f"Config Directory: [{config_status}] {results['config_dir']['message']}")
    
    # Installation status
    install_status = "✓" if results["install_status"]["result"] else "✗"
    print(f"Installation: [{install_status}] {results['install_status']['message']}")
    
    # Auth module check
    auth_status = "✓" if results["auth_module"]["result"] else "✗"
    print(f"Auth Module: [{auth_status}] {results['auth_module']['message']}")
    
    # Overall status
    print("\n" + "-" * 80)
    overall_status = "✓" if results["overall"]["result"] else "✗"
    print(f"Overall Status: [{overall_status}] {results['overall']['message']}")
    print("-" * 80 + "\n")
    
    # Recommendations if issues exist
    if not results["overall"]["result"]:
        print("Recommendations:")
        
        if not results["python_version"]["result"]:
            print("- Upgrade Python to version 3.7 or higher")
        
        if not results["required_packages"]["result"]:
            print("- Install required packages with:")
            missing = []
            for i, (passed, message) in enumerate(results["required_packages"]["details"]):
                if not passed:
                    pkg_name, min_version = REQUIRED_PACKAGES[i]
                    missing.append(f"{pkg_name}>={min_version}")
            print(f"  pip install {' '.join(missing)}")
        
        if not results["config_dir"]["result"]:
            print(f"- Create config directory manually and ensure it's writable")
            
        if not results["install_status"]["result"]:
            print("- Install the package with: pip install -e .")
        
        print()
    
    if not results["credentials"]["result"]:
        print("To use the application, you need Google API credentials:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Create a project and enable Drive API and Drive Labels API")
        print("3. Create OAuth credentials for a desktop application")
        print("4. Download the credentials and save as 'credentials.json' in project directory")
        print("   or in the config directory mentioned above")
        print()
    
    if not results["optional_packages"]["result"]:
        print("For visualization features, install optional packages:")
        print("  pip install pandas matplotlib seaborn")
        print()


def check_test_environment() -> Tuple[bool, str]:
    """
    Check if the environment is set up for running tests without authentication.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        test_imports = ["unittest", "unittest.mock"]
        for module in test_imports:
            importlib.import_module(module)
            
        # Check if test directory exists
        if Path("tests").is_dir():
            # Check for test files
            test_files = list(Path("tests").glob("test_*.py"))
            if test_files:
                return True, f"Test environment is ready ({len(test_files)} test files found)"
            else:
                return False, "Test directory exists but no test files found"
        else:
            return False, "Test directory not found"
    except ImportError as e:
        return False, f"Missing required testing module: {e}"
    except Exception as e:
        return False, f"Error checking test environment: {e}"


def run_tests() -> Tuple[bool, str]:
    """
    Run the test suite.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        import unittest
        import io
        import sys
        
        # Capture stdout to display test results
        original_stdout = sys.stdout
        test_output = io.StringIO()
        sys.stdout = test_output
        
        # Run tests in discovery mode
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Restore stdout and get the captured output
        sys.stdout = original_stdout
        output = test_output.getvalue()
        
        # Print the test output
        print(output)
        
        # Check results
        if result.failures or result.errors:
            return False, f"Tests failed: {len(result.failures)} failures, {len(result.errors)} errors"
        else:
            return True, f"All tests passed ({result.testsRun} tests run)"
    except Exception as e:
        return False, f"Error running tests: {e}"


def setup_development_environment() -> None:
    """Set up the development environment for testing."""
    try:
        print("\nSetting up development environment...")
        
        # Install package in development mode
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-e", "."
        ])
        
        # Install development dependencies
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "pytest", "coverage"
        ])
        
        print("Development environment set up successfully")
    except subprocess.CalledProcessError as e:
        print(f"Failed to set up development environment: {e}")
    except Exception as e:
        print(f"Error during setup: {e}")


def main():
    """Main function to run the pre-check script."""
    print("Running environment check for Legal Drive Labels Manager...")
    
    try:
        # Run all checks
        results = run_all_checks()
        
        # Print results
        print_results(results)
        
        # Try to fix issues if needed
        if not results["overall"]["result"] or not results["optional_packages"]["result"]:
            print("Would you like to try to fix the issues automatically? (y/n)")
            response = input().lower()
            if response.startswith('y'):
                fix_common_issues(results)
                
                # Re-run checks to see if issues were fixed
                print("\nRe-checking environment after fixes...")
                results = run_all_checks()
                print_results(results)
        
        # Check if user wants to run tests
        if results["install_status"]["result"]:
            print("Would you like to check the test environment? (y/n)")
            response = input().lower()
            if response.startswith('y'):
                test_env_success, test_env_message = check_test_environment()
                print(f"\nTest Environment: {'✓' if test_env_success else '✗'} {test_env_message}")
                
                if test_env_success:
                    print("\nWould you like to run the tests? (y/n)")
                    response = input().lower()
                    if response.startswith('y'):
                        test_success, test_message = run_tests()
                        print(f"\nTest Results: {'✓' if test_success else '✗'} {test_message}")
                else:
                    print("\nWould you like to set up the development environment? (y/n)")
                    response = input().lower()
                    if response.startswith('y'):
                        setup_development_environment()
        
        return 0 if results["overall"]["result"] else 1
        
    except KeyboardInterrupt:
        print("\nCheck aborted by user.")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"\nUnexpected error during environment check: {e}")
        print("\nStacktrace:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())