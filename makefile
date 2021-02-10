.PHONY: package venv

VERSION=0.9rc1

venv: venv/pyvenv.cfg

package: dist/dfsimage-$(VERSION).tar.gz

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

doc/_build/.stamp: readme.rst doc/conf.py
	python -m sphinx . doc/_build readme.rst -c doc && touch $@
