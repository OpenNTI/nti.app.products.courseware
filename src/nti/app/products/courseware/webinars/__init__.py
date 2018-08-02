#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

WEBINAR_ASSET_MIME_TYPE = 'application/vnd.nextthought.webinarasset'

logger = __import__('logging').getLogger(__name__)


def _register():
    try:
        from nti.solr.presentation import ASSETS_CATALOG
        from nti.solr.utils import mimeTypeRegistry
        mimeTypeRegistry.register(WEBINAR_ASSET_MIME_TYPE, ASSETS_CATALOG)
    except ImportError:
        logger.warning("Solr registry is not available")


_register()
del _register
