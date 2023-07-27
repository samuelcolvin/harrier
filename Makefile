.DEFAULT_GOAL := all
isort = isort harrier tests
black = black -S -l 120 --target-version py310 harrier tests

.PHONY: install
install:
	pip install -U setuptools pip
	pip install -U -r tests/requirements.txt
	pip install -U -e .

.PHONY: format
format:
	$(isort)
	$(black)

.PHONY: lint
lint:
	flake8 harrier/ tests/
	$(isort) --check-only --df
	$(black) --check

.PHONY: check-dist
check-dist:
	python setup.py check -ms
	python setup.py sdist
	twine check dist/*

.PHONY: test
test:
	pytest --cov=harrier

.PHONY: testcov
testcov:
	pytest --cov=harrier
	@echo "building coverage html"
	@coverage combine
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
