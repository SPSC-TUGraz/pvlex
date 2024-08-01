import setuptools

with open("README.md", "r", encoding="utf-8") as fd:
    long_description = fd.read()

setuptools.setup(
    name="swekia", # Replace with your own username
    version="0.0.1",
    author="Saskia Wepner",
    author_email="wepner@tugraz.at",
    description="Create pronunciation lexicon with variants for Austrian German conversational speech.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="https://gitlab.tugraz.at/",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "json5",
        "numpy",
        "os",
        "pandas",
        "regex",
        "sys"
    ]
)
