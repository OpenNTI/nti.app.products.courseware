#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from zope.traversing.interfaces import IPathAdapter

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def course_badges(course, unused_request):
    return ICourseAcclaimBadgeContainer(course)
