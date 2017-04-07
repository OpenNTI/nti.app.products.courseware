#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.schema.field import Bool
from nti.schema.field import ValidTextLine as TextLine


class ICourseInvitation(interface.Interface):
    Code = TextLine(title="Invitation code.", required=True)
    Scope = TextLine(title="The enrollment scope.", required=True)
    Description = TextLine(title="The invitation description.", required=True)
    Course = TextLine(title="Course catalog entry NTIID.", required=False)
    Course.setTaggedValue('_ext_excluded_out', True)
    IsGeneric = Bool(title="Invitation code is generic.",
                     required=False,
                     default=False)
    IsGeneric.setTaggedValue('_ext_excluded_out', True)
