#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.namedfile.file import FileConstraints

@component.adapter(ICourseDiscussion)
class _CourseDiscussionFileConstraints(FileConstraints):
	max_file_size = 10485760  # 10 MB
