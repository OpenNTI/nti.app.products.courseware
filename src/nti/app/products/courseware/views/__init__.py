#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory
from .. import VIEW_CONTENTS
from .. import VIEW_COURSE_ACTIVITY
from .. import VIEW_CATALOG_ENTRY
from .. import VIEW_COURSE_RECURSIVE
from .. import VIEW_COURSE_ENROLLMENT_ROSTER
from .. import VIEW_COURSE_RECURSIVE_BUCKET

VIEW_CONTENTS = VIEW_CONTENTS
VIEW_COURSE_ACTIVITY = VIEW_COURSE_ACTIVITY
VIEW_CATALOG_ENTRY = VIEW_CATALOG_ENTRY
VIEW_COURSE_RECURSIVE = VIEW_COURSE_RECURSIVE
VIEW_COURSE_ENROLLMENT_ROSTER = VIEW_COURSE_ENROLLMENT_ROSTER
VIEW_COURSE_RECURSIVE_BUCKET = VIEW_COURSE_RECURSIVE_BUCKET
