from setuptools import setup, find_packages

setup(
    name="scheduler-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "scheduler=cli.scheduler_cli:cli",
        ],
    },
)
