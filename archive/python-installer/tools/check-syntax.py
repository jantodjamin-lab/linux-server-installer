"""Offline syntax check without compileall bytecode writes."""
import ast
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
for directory in ('lib','tools','tests','release'):
    for path in sorted((BASE/directory).glob('*.py')):
        ast.parse(path.read_text(),filename=str(path))
print('Python AST syntax: PASS (no bytecode writes)')
