import pytest


def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Tester avec PostgreSQL sur 55433")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Activer avec --integration et Docker"))
