Install requirements:

    sudo apt-get install pandoc
    pip install wheel pypandoc

To upload to pypi (assuming version has been incremented):

    python setup.py sdist bdist_wheel upload -r pypi
