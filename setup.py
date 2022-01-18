import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="python_solana_nft_snapshot",
    version="0.0.1",
    author="Bill Hewitt",
    author_email="bill@bhewitt.org",
    description="Python tooling to snapshot and analyze Solana NFT projects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bill-hewitt/python_solana_nft_snapshot",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=["Programming Language :: Python :: 3", "Operating System :: OS Independent"],
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    python_requires=">=3.9",
    install_requires=[
        "aiohttp",
        "aiolimiter",
        "asyncio",
        "base58",
        "pandas",
        "retry",
        "solana",
        "tqdm",
    ],
    tests_require=["mock", "pytest", "pytest-mock"],
)
