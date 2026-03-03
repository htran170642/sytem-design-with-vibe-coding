"""Setup script for AIVA package."""
from setuptools import setup, find_packages

setup(
    name="aiva",
    version="0.1.0",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        # Dependencies are managed in requirements.txt
    ],
    python_requires=">=3.11",
)