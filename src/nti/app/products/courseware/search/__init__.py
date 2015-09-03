#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from ..utils import DEFAULT_EXP_TIME

from ..utils import encode_keys
from ..utils import memcache_get
from ..utils import memcache_set
from ..utils import memcache_client
from ..utils import last_synchronized
