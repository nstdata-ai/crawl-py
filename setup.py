from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="nstdata-ai-crawl",
    version="0.1.1",
    packages=find_packages(),
    install_requires=[
        "requests>=2.0.0",
    ],
    author="nstdata-ai",
    author_email="github@nstproxy.com",
    description="Python SDK for nstdata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nstdata-ai/crawl-py",
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
