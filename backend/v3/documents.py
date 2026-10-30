"""Compatibility import for the document service moved to backend.core.

Existing scripts importing backend.v3.documents continue to use the same functions.
"""
from ..core.documents import setup,save,get,listing,history

__all__=['setup','save','get','listing','history']
