"""
Setup script for Politia
"""
from setuptools import setup, find_packages

setup(
    name="politia",
    version="0.1.0",
    description="Politia Data Engineering System - Parliamentary Data Pipeline and API",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "sqlalchemy>=2.0.23",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.2",
        "lxml>=4.9.3",
        "loguru>=0.7.2",
    ],
    python_requires=">=3.8",
)


