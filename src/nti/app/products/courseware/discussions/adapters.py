#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.namedfile.constraints import FileConstraints

from nti.namedfile.interfaces import IFileConstraints


@component.adapter(ICourseDiscussion)
@interface.implementer(IFileConstraints)
class _CourseDiscussionFileConstraints(FileConstraints):
    max_files = 2
    max_file_size = 10485760  # 10 MB
