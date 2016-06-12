# ----------------------------------------------------------------------
# Copyright (c) 2014 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

from __future__ import division

#--------------------
# System wide imports
# -------------------

import sys

# ---------------
# Twisted imports
# ---------------

#--------------
# local imports
# -------------

from ._version import get_versions

# ----------------
# Module constants
# ----------------

PY2 = sys.version_info[0] == 2

# -----------------------
# Module global variables
# -----------------------

__version__ = get_versions()['version']



del get_versions
