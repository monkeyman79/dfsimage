.PHONY: package venv

VERSION=0.9rc3

venv: venv/pyvenv.cfg

package: dist/dfsimage-$(VERSION).tar.gz

doc: doc/_build/.stamp

clean:
	rm -r venv dist build dfsimage.egg-info

test:
	bash -c 'source venv/bin/activate && pytest'

venv/pyvenv.cfg: dist/dfsimage-$(VERSION).tar.gz
	python -m venv venv
	bash -c 'source venv/bin/activate && pip install dist/dfsimage-$(VERSION).tar.gz && \
		pip install pytest'

dist/dfsimage-$(VERSION).tar.gz:
	python -m build

doc/_build/.stamp: readme.rst dfsimage/*.py doc/*.rst doc/conf.py
	python -m sphinx doc doc/_build && touch $@
