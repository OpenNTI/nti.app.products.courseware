#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

class ICourseOutlineCache(interface.Interface):
    """
    marker interface for a content search outline cache
    """
    
    def is_allowed(ntiid, query=None, now=None):
        """
        returns true if the specified query is allowed over the specified NTIID
        
        :param ntiid: The [container] NTIID
        :param query: The search query
        :param now: Current time
        """
