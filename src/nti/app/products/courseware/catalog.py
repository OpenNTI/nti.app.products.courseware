#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "moved to nti.contenttypes.courses",
    "nti.contenttypes.courses.catalog",
    "CourseCatalog",
    "CourseCatalogInstructorInfo",
    "CourseCatalogEntry")
