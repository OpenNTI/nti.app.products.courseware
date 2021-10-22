#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IRolePermissionMap
from zope.securitypolicy.interfaces import IPrincipalPermissionMap

from zope.securitypolicy.settings import Unset

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.users.utils import get_site_admins

from nti.dataserver.interfaces import ISiteAdminUtility

from nti.dataserver.users import User

from nti.contenttypes.courses.common import get_course_site_name

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope

from nti.coremetadata.interfaces import IShareableModeledContent

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization import is_site_admin

from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


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


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IPrincipalPermissionMap)
class CourseInstanceEnrollmentPrincipalPermissionMap(object):
    """
    Ensure our site admins have access to users in their site enrollment records.
    """

    SITE_ADMIN_PERM_IDS = (ACT_READ.id,)

    def __init__(self, context):
        self.context = context
        self._user = User.get_user(context.Username)

    @Lazy
    def siteAdminUtility(self):
        return component.getUtility(ISiteAdminUtility)

    def _can_admin(self, site_admin):
        return self.siteAdminUtility.can_administer_user(site_admin,
                                                         self._user)

    @Lazy
    def _effectiveAdminsForUser(self):
        result = [site_admin.username for site_admin in get_site_admins()
                  if self._can_admin(site_admin)]
        result.append(ROLE_ADMIN.id)
        return result

    def getPrincipalsForPermission(self, perm):
        result = []
        if perm in self.SITE_ADMIN_PERM_IDS:
            for principal_id in self._effectiveAdminsForUser:
                result.append((principal_id, Allow))
        return result

    def getPermissionsForPrincipal(self, principal_id):
        if principal_id in self._effectiveAdminsForUser:
            return [(perm, Allow) for perm in self.SITE_ADMIN_PERM_IDS]

        return []

    def getSetting(self, permission_id, principal_id, default=Unset):
        if permission_id in self.SITE_ADMIN_PERM_IDS:
            if principal_id in self._effectiveAdminsForUser:
                return Allow

        return default

    def getPrincipalsAndPermissions(self):
        result = []
        for principal_id in self._effectiveAdminsForUser:
            for perm in self.SITE_ADMIN_PERM_IDS:
                result.append((principal_id, perm, Allow))
        return result


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IRolePermissionMap)
class CourseInstanceEnrollmentRolePermissionMap(object):
    """
    Ensure our admins have access to users' enrollment records.
    """

    ADMIN_PERM_IDS = (ACT_READ.id,)
    ADMIN_ID = ROLE_ADMIN.id

    def __init__(self, context):
        self.context = context

    def getRolesForPermission(self, perm):
        result = []
        if perm in self.ADMIN_PERM_IDS:
            result.append((self.ADMIN_ID, Allow))
        return result

    def getPermissionsForRole(self, role_id):
        if role_id == self.ADMIN_ID:
            return [(perm, Allow) for perm in self.ADMIN_PERM_IDS]
        return []

    def getSetting(self, permission_id, role_id, default=Unset):
        if permission_id in self.ADMIN_PERM_IDS:
            if role_id == self.ADMIN_ID:
                return Allow
        return default

    def getRolesAndPermissions(self):
        result = []
        for perm in self.ADMIN_PERM_IDS:
            result.append((self.ADMIN_ID, perm, Allow))
        return result