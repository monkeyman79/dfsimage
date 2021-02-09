doc/_build/.stamp: readme.rst doc/conf.py
	python -m sphinx . doc/_build readme.rst -c doc && touch $@