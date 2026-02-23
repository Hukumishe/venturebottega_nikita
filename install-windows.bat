@echo off
REM Quick install script for Windows
REM This installs packages using pre-built wheels to avoid compilation issues

echo Installing Politia dependencies...
echo.

echo Step 1: Installing pydantic (pre-built wheels)...
pip install --only-binary :all: pydantic pydantic-settings
if errorlevel 1 (
    echo ERROR: Failed to install pydantic
    exit /b 1
)

echo.
echo Step 2: Installing lxml (pre-built wheels)...
pip install --only-binary :all: lxml
if errorlevel 1 (
    echo ERROR: Failed to install lxml
    exit /b 1
)

echo.
echo Step 3: Installing remaining dependencies...
pip install fastapi uvicorn[standard] sqlalchemy python-dotenv requests beautifulsoup4 loguru
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

echo.
echo Installation complete!
echo.
echo You can now run:
echo   python scripts/run_pipeline.py  - to process data
echo   python scripts/run_api.py        - to start the API server






