from setuptools import setup, find_packages
from pathlib import Path
import re
from urllib.parse import urljoin

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")
repository = "https://github.com/nstdata-ai/crawl-py"
# PyPI renders metadata outside the repository's relative-link context.
long_description = re.sub(
    r'(\[[^\]\n]+\]\()([^\)\n]+)(\))',
    lambda match: match[1] + urljoin(repository + '/blob/main/README.md', match[2]) + match[3],
    long_description,
)

setup(
    name="nstdata-ai-crawl",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.34.2,<3",
    ],
    author="nstdata-ai",
    author_email="github@nstproxy.com",
    description="Python client for Nstdata Crawl",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=repository,
    project_urls={
        "Documentation": repository + "/blob/main/docs/guide.md",
        "Source": repository,
        "Issues": repository + "/issues",
    },
    python_requires=">=3.10",
    license_expression="MIT",
    license_files=["LICENSE"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
