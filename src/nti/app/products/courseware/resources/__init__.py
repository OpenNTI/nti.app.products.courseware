#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#: Course resources
RESOURCES = 'resources'

from nti.app.products.courseware.resources.model import CourseRootFolder
from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentImage
from nti.app.products.courseware.resources.model import CourseContentFolder
