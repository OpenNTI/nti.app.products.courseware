#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: site.py 129822 2018-06-20 16:11:30Z josh.zuech $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.interfaces import IHostPolicyFolder

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInvitation)
@interface.implementer(IPrincipalRoleManager)
def invitation_role_manager(course_invitation):
    # This is a hack, invitations are lineaged under ds2, but we want site
    # admins to be able to manage them. Here we swap out the PRM for the
    # relevant course site as the ICourseInvitation PRM.
    entry_ntiid = course_invitation.Course
    entry = find_object_with_ntiid(entry_ntiid)
    course = ICourseInstance(entry, None)
    site = IHostPolicyFolder(course, None)
    return IPrincipalRoleManager(site, None)
