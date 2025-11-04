"""Entry point for running ihe_test_util as a module.

This allows the package to be executed as:
    python -m ihe_test_util
"""

from ihe_test_util.cli.main import cli

if __name__ == "__main__":
    cli()
