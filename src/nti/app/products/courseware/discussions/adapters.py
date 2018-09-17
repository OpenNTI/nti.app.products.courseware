#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.namedfile.constraints import FileConstraints

from nti.namedfile.interfaces import IFileConstraints

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseDiscussion)
@interface.implementer(IFileConstraints)
class _CourseDiscussionFileConstraints(FileConstraints):
    max_files = 2
    max_file_size = 10485760  # 10 MB
