#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import INotableFilter


@interface.implementer(INotableFilter)
class CourseCalendarEventNotableFilter(object):

    def __init__(self, context):
        self.context = context

    def is_notable(self, obj, user):
        return True
