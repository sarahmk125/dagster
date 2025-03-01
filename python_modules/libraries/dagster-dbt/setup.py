from typing import Dict

from setuptools import find_packages, setup  # type: ignore


def get_version() -> str:
    version: Dict[str, str] = {}
    with open("dagster_dbt/version.py") as fp:
        exec(fp.read(), version)  # pylint: disable=W0122

    return version["__version__"]


if __name__ == "__main__":
    setup(
        name="dagster-dbt",
        version=get_version(),
        author="Elementl",
        author_email="hello@elementl.com",
        license="Apache-2.0",
        description="A Dagster integration for dbt",
        url="https://github.com/dagster-io/dagster/tree/master/python_modules/libraries/dagster-dbt",
        classifiers=[
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: OS Independent",
        ],
        packages=find_packages(exclude=["test"]),
        install_requires=[
            "dagster",
            "dagster-pandas",
            "pandas",
            "requests",
            "attrs",
            "agate < 1.6.2",
        ],
        extras_require={
            "test": [
                # https://github.com/dagster-io/dagster/issues/4167
                "Jinja2<3.0",
                "dbt>=0.17.0",
                "matplotlib",
            ]
        },
        zip_safe=False,
    )
