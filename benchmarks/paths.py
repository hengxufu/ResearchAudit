"""Keep disposable benchmark state outside the source tree's top-level listing."""
from pathlib import Path

def temporary_root():
    root=Path(__file__).resolve().parents[1]/'.artifacts'/'test-runs'
    root.mkdir(parents=True,exist_ok=True)
    return root
