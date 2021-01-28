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

from zope.cachedescriptors.property import Lazy

from zope.security.interfaces import IPrincipal

from nti.app.products.courseware.interfaces import IEnrolledCoursesCollection
from nti.app.products.courseware.interfaces import ICourseIntegrationCollection
from nti.app.products.courseware.interfaces import IAdministeredCoursesCollection

from nti.coremetadata.interfaces import ISupplementalACLProvider

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IACLProvider)
class CollectionACLProviderMixin(object):

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        user = self.context.__parent__.user
        aces = [ace_allowing(IPrincipal(user), (ALL_PERMISSIONS), type(self))]
        aces.append(ACE_DENY_ALL)
        return acl_from_aces(aces)


@component.adapter(IEnrolledCoursesCollection)
class EnrolledCoursesCollectionACLProvider(CollectionACLProviderMixin):
    pass


@component.adapter(IAdministeredCoursesCollection)
class AdministeredCoursesCollectionACLProvider(CollectionACLProviderMixin):
    pass


@interface.implementer(IACLProvider)
@component.adapter(ICourseIntegrationCollection)
class CourseIntegrationCollectionACLProvider(object):

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        aces = []
        for supplemental in component.subscribers((self.context,),
                                                  ISupplementalACLProvider):
            for supplemental_ace in supplemental.__acl__ or ():
                if supplemental_ace is not None:
                    aces.append(supplemental_ace)
        acl = acl_from_aces(aces)
        return acl
