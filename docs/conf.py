"""Sphinx configuration for khatt's documentation (https://dressam97.github.io/khatt/)."""

from __future__ import annotations

import re
from typing import Any

import khatt

project = "khatt"
author = "Mohammed Essam"
copyright = "2026, Mohammed Essam"
release = version = khatt.__version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
exclude_patterns = ["_build"]

# The README is the front page: its in-page links (#install) need heading anchors.
myst_heading_anchors = 3
myst_enable_extensions = ["colon_fence"]

# khatt.video needs moviepy (the video extra); the docs only need its signatures.
autodoc_mock_imports = ["moviepy"]
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_preserve_defaults = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pillow": ("https://pillow.readthedocs.io/en/stable", None),
}

html_theme = "furo"
html_title = f"khatt {release}"
html_favicon = None
html_theme_options = {
    "source_repository": "https://github.com/DrEssam97/khatt",
    "source_branch": "main",
    "source_directory": "docs/",
}
copybutton_prompt_text = r"\$ "
copybutton_prompt_is_regexp = True


REPOSITORY = "https://github.com/DrEssam97/khatt/blob/main/"
# Links in the README and CHANGELOG to files that are not doc pages (LICENSE,
# pyproject.toml, CONTRIBUTING.md, the font licences) point at the repository.
_REPO_FILE = re.compile(r"\]\((?!https?://|#|docs/|mailto:)([^)\s]+)\)")


def _link_repository_files(
    app: Any, relative_path: Any, parent_docname: str, content: list[str]
) -> None:
    content[0] = _REPO_FILE.sub(lambda match: f"]({REPOSITORY}{match.group(1)})", content[0])


def setup(app: Any) -> None:
    app.connect("include-read", _link_repository_files)
