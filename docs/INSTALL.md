# Installation Guide

## Quick Install (Recommended for Windows)

If you encounter Rust or C++ compilation errors, install packages with pre-built wheels:

```bash
# Install pydantic with pre-built wheels (avoids Rust compilation)
pip install --only-binary :all: pydantic pydantic-settings

# Install lxml with pre-built wheels (avoids C++ compilation)
pip install --only-binary :all: lxml

# Install remaining dependencies
pip install fastapi uvicorn[standard] sqlalchemy python-dotenv requests beautifulsoup4 loguru
```

This approach uses only pre-compiled packages and avoids compilation issues.

## Standard Install

```bash
pip install -r requirements.txt
```

## Troubleshooting Rust/Cargo Errors

If you see errors about Rust or Cargo not being found:

### Option 1: Use Pre-built Wheels (Easiest)

```bash
pip install --only-binary :all: pydantic pydantic-settings
pip install -r requirements.txt
```

### Option 2: Install Rust (For Full Compatibility)

1. **Windows:**
   - Download and run the installer from https://rustup.rs/
   - Or use: `winget install Rustlang.Rustup` (if you have winget)

2. **After installing Rust:**
   ```bash
   rustup default stable
   pip install -r requirements.txt
   ```

### Option 3: Use Alternative Pydantic Version

If you continue to have issues, you can use Pydantic 1.x (requires code changes):

```bash
pip install "pydantic<2.0.0" "pydantic-settings<2.0.0"
```

**Note:** This requires updating the code to use Pydantic 1.x syntax (change `model_config` to `Config` class with `orm_mode = True`).

## Python Version Requirements

- Python 3.8 or higher
- pip 21.0 or higher (for proper wheel support)

## Verify Installation

```bash
python -c "import pydantic; print(pydantic.__version__)"
python -c "import fastapi; print(fastapi.__version__)"
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

All should print version numbers without errors.

