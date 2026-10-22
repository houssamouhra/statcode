PREFIX    ?= /usr
BINDIR    := $(PREFIX)/bin
LIBDIR    := $(PREFIX)/lib/statcode

BUILD_DIR := build
DIST_NAME := statcode-dist
DIST_DIR  := $(BUILD_DIR)/$(DIST_NAME).dist
BINARY    := $(DIST_DIR)/statcode

.PHONY: build install clean

build:
	@echo "Building statcode..."
	uv run python -m nuitka \
		--mode=standalone \
		--output-filename=statcode \
		--output-dir=$(BUILD_DIR) \
		--output-folder-name=$(DIST_NAME) \
		--include-package=urwid \
		--include-package=yaml \
		--nofollow-import-to=doctest \
		--include-data-files="src/statcode/*.yml=statcode-data/" \
		src/statcode
	@echo ""
	@echo "Build complete: $(BINARY)"


install: build
	install -Dm755 $(BINARY) $(DESTDIR)$(LIBDIR)/statcode
	cp -a $(DIST_DIR)/. $(DESTDIR)$(LIBDIR)/
	install -d $(DESTDIR)$(BINDIR)
	ln -sfn $(LIBDIR)/statcode $(DESTDIR)$(BINDIR)/statcode
	@echo "Installed statcode to $(DESTDIR)$(BINDIR)/statcode"

clean:
	rm -rf $(BUILD_DIR) src/statcode/__pycache__
	@echo "Build artifacts removed."
