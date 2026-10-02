import pytest


@pytest.fixture(scope="session")
def django_db_setup():
    """Skip test-database creation — queries run against the real database in settings.py."""
    pass
