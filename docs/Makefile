# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = dill
SOURCEDIR     = source
BUILDDIR      = build

# Internal variables
ALLSPHINXOPTS = $(SPHINXOPTS) $(SOURCEDIR)

# Put it first so that "make" without argument is like "make help".
help:
	@echo "Please use \`make html' to generate standalone HTML files"

.PHONY: help clean html Makefile

clean:
	-rm -rf $(BUILDDIR)

html:
	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) $(BUILDDIR)
	-rm -f $(BUILDDIR)/../../scripts/_*py
	-rm -f $(BUILDDIR)/../../scripts/_*pyc
	-rm -rf $(BUILDDIR)/../../scripts/__pycache__

