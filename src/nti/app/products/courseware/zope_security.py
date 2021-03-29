#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.component.hooks import getSite

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalPermissionMap

from zope.securitypolicy.settings import Unset

from nti.contenttypes.courses.common import get_course_site_name

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope

from nti.coremetadata.interfaces import IShareableModeledContent

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization import is_site_admin

from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface


@component.adapter(IShareableModeledContent)
@interface.implementer(IPrincipalPermissionMap)
class ShareableModeledContentSiteAdminPermissionMap(object):

    SITE_ADMIN_PERM_IDS = (ACT_READ.id,)

    def __init__(self, context):
        self.context = context

    def getPrincipalsForPermission(self, perm):
        # This is a no-op
        return []

    def _is_principal_allowed(self, principal_id):
        """
        If this context is shared with *any* :class:`ICourseInstanceSharingScope`,
        we add the site all course instance sharing scope principal to the ACL.

        Note, this approach will make sure the site admin has dynamic READ access
        to the UGD, but we currently are not doing anything to ensure this UGD
        is visible to site admins in any other context (search, etc).
        """
        if not is_site_admin(principal_id):
            return False
        for sharing_target in self.context.sharingTargetNames or ():
            if is_valid_ntiid_string(sharing_target):
                shared_with_obj = find_object_with_ntiid(sharing_target)
                if ICourseInstanceSharingScope.providedBy(shared_with_obj):
                    # We found a scope; this must be a scope from a single course
                    # and a single site.
                    course = find_interface(shared_with_obj, ICourseInstance, strict=False)
                    if get_course_site_name(course) == getSite().__name__:
                        return True
        return False

    def getPermissionsForPrincipal(self, principal_id):
        if self._is_principal_allowed(principal_id):
            return [(perm, Allow) for perm in self.SITE_ADMIN_PERM_IDS]
        return []

    def getSetting(self, permission_id, principal_id, default=Unset):
        if permission_id in self.SITE_ADMIN_PERM_IDS:
            if self._is_principal_allowed(principal_id):
                return Allow
        return default

    def getPrincipalsAndPermissions(self):
        # This is a no-op
        return []
