#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrated courseware-related interfaces. This
is a high-level package built mostly upon the low-level
datastructures defined in :mod:`nti.app.products.courses`.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

class ICourseCatalog(interface.Interface):
	"""
	Something that manages the set of courses
	available in the system and provides
	ways to query for courses and find
	out information about them.
	"""

	# TODO: What is this a specialization of, anything?
