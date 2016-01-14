#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.products.courseware.utils import DEFAULT_EXP_TIME

from nti.app.products.courseware.utils import encode_keys
from nti.app.products.courseware.utils import memcache_get
from nti.app.products.courseware.utils import memcache_set
from nti.app.products.courseware.utils import memcache_client
from nti.app.products.courseware.utils import last_synchronized
