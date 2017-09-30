#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.dataserver.interfaces import ICreatableObjectFilter

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICreatableObjectFilter)
class _CoursesContentObjectFilter(object):

    TO_FILTER = ("application/vnd.nextthought.courses.coursecataloginstructorinfo",
                 "application/vnd.nextthought.courses.coursesynchronizationresults",
                 "application/vnd.nextthought.courseware.courseinstanceadministrativerole")

    def __init__(self, context=None):
        pass

    def filter_creatable_objects(self, terms):
        for name in self.TO_FILTER:
            if name in terms:
                terms.pop(name, None)
        return terms
