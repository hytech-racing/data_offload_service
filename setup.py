from setuptools import setup, find_packages

setup(
    name="data_offload_service",
    version="1.0",
    packages=find_packages(),
    scripts=['offload.py']
)