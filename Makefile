.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -U -r tests/requirements.txt
	pip install -U .

.PHONY: isort
isort:
	isort -rc -w 120 harrier
	isort -rc -w 120 tests

.PHONY: lint
lint:
	python setup.py check -rms
	flake8 harrier/ tests/
	pytest harrier -p no:sugar -q

.PHONY: test
test:
	pytest --cov=harrier

.PHONY: testcov
testcov:
	pytest --cov=harrier
	@echo "building coverage html"
	@coverage html

.PHONY: all
all: testcov lint

.PHONY: clean
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -rf .cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	python setup.py clean
	make -C docs clean
