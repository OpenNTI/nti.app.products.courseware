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


def has_completed_course(user, course, success_only=False):
    """
    Answers if the user has completed the given course (and successfully if success_only is True). Will return False if
    the course is not completable (or is not successfully completed if success_only is True).
    """
    policy = ICompletionContextCompletionPolicy(course, None)
    result = False
    if policy is not None:
        progress = component.queryMultiAdapter((user, course), IProgress)
        result = policy.is_complete(progress)
        result = bool(result and result.Success) if success_only else bool(result)
    return result
