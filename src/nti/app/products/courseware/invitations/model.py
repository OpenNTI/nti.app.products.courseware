#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.externalization.representation import WithRepr

from nti.schema.eqhash import EqHash

from nti.schema.field import SchemaConfigured

from nti.schema.fieldproperty import createDirectFieldProperties


@WithRepr
@EqHash('Code')
@interface.implementer(ICourseInvitation)
class CourseInvitation(SchemaConfigured):
    createDirectFieldProperties(ICourseInvitation)

    @property
    def isGeneric(self):
        return self.IsGeneric
