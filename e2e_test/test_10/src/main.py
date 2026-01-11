"""
Main module for the project.
Imports helper functions from utils module.
"""

from utils import helper_function


def main():
    """Main entry point."""
    result = helper_function("test")
    print(f"Result: {result}")
    return result


if __name__ == "__main__":
    main()
