#!/usr/bin/env python3
"""Test if all dependencies are installed correctly"""
import sys

try:
    import pydantic
    print(f"[OK] pydantic {pydantic.__version__}")
except ImportError as e:
    print(f"[ERROR] pydantic: {e}")
    sys.exit(1)

try:
    import fastapi
    print(f"[OK] fastapi {fastapi.__version__}")
except ImportError as e:
    print(f"[ERROR] fastapi: {e}")
    sys.exit(1)

try:
    import sqlalchemy
    print(f"[OK] sqlalchemy {sqlalchemy.__version__}")
except ImportError as e:
    print(f"[ERROR] sqlalchemy: {e}")
    sys.exit(1)

try:
    import lxml
    print(f"[OK] lxml {lxml.__version__}")
except ImportError as e:
    print(f"[ERROR] lxml: {e}")
    sys.exit(1)

print("\n[SUCCESS] All core dependencies installed successfully!")
print("You can now run the pipeline and API server.")

