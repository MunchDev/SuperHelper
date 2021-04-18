venv:
	python3 -m venv .venv
	./.venv/bin/pip3 install -r requirements.txt

build:
	python3 setup.py sdist bdist_wheel

publish: build
	twine check dist/* && twine upload dist/*

dev-install:
	pip3 install -e .

test:
	rm -rf .test_dir && mkdir .test_dir
	export SUPER_HELPER_APP_DIR=./.test_dir && pytest --cov

docs: docs-html docs-pdf

docs-pdf:
	@pdoc --pdf -f src/SuperHelper > .docs
	@pandoc --metadata=title:"MyProject Documentation" --from=markdown+abbreviations+tex_math_single_backslash \
	--pdf-engine=xelatex --variable=mainfont:"DejaVu Sans" --toc --toc-depth=4 --output=documentation.pdf .docs
	@rm .docs

docs-html:
	pdoc --html -fo docs/ src/SuperHelper

clean-all: clean clean-cfg clean-test

clean:
	pip3 uninstall -y SuperHelper && rm -rf src/*.egg-info
	rm -rf build/ dist/ .coverage
	find . -type d -name __pycache__ -exec rm -r {} \+

clean-cfg:
	rm -rf ~/Library/Application\ Support/SuperHelper/ ~/.config/SuperHelper

clean-test:
	rm -rf .test_dir .pytest_cache coverage.xml .coverage
	rm -rf .coverage.*
