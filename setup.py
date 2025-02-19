import setuptools

with open("Readme.md", "r", encoding="utf-8") as fd:
    long_description = fd.read()

setuptools.setup(
    name="pvlex",
    version="1.0",
    author="Saskia Wepner",
    author_email="wepner@tugraz.at",
    description="Create pronunciation lexicon with variants for Austrian German conversational speech.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SPSC-TUGraz/pvlex",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU GENERAL PUBLIC LICENSE",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "json5",
        "numpy",
        "pandas",
        "regex"
    ]
)
