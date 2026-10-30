"""All disposable pytest state lives under the ignored workspace artifact tree."""
from pathlib import Path
from uuid import uuid4

def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp=str(Path(__file__).resolve().parents[1]/'.artifacts'/'test-runs'/('pytest-'+uuid4().hex))
    # Pytest creates basetemp itself but requires its parent to exist.
    Path(config.option.basetemp).resolve().parent.mkdir(parents=True,exist_ok=True)
