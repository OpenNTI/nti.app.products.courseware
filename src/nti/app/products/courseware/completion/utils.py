#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

logger = __import__('logging').getLogger(__name__)


def has_completed_course(user, course):
    """
    Answers if the user has completed the given course. Will return False if
    the course is not completable.
    """
    policy = ICompletionContextCompletionPolicy(course, None)
    result = False
    if policy is not None:
        progress = component.queryMultiAdapter((user, course), IProgress)
        result = bool(policy.is_complete(progress))
    return result

