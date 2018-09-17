#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.externalization.representation import WithRepr

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)


@WithRepr
@EqHash('Code')
@interface.implementer(ICourseInvitation)
class CourseInvitation(SchemaConfigured):
    createDirectFieldProperties(ICourseInvitation)

    __parent__ = None
    __name__ = alias('code')

    code = alias('Code')
    scope = alias('Scope')
    course = alias('Course')
    isGeneric = alias('IsGeneric')
    description = alias('Description')

    creator = SYSTEM_USER_ID

    def __str__(self):
        return self.code


@interface.implementer(ICourseInvitation)
class PersistentCourseInvitation(PersistentCreatedModDateTrackingObject,
                                 CourseInvitation): # order matters
    """
    A persistent version of CourseInvitation
    """
    __external_can_create__ = True
    __external_class_name__ = 'CourseInvitation'

    _SET_CREATED_MODTIME_ON_INIT = True

    mimeType = mime_type = "application/vnd.nextthought.courseware.courseinvitation"
