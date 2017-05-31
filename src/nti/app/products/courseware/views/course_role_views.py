#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zope.cachedescriptors.property import Lazy

from zope.event import notify

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import VIEW_COURSE_EDITORS
from nti.app.products.courseware import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware import VIEW_COURSE_REMOVE_INSTRUCTORS

from nti.app.products.courseware.views import raise_error

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import CourseEditorAddedEvent
from nti.contenttypes.courses.interfaces import CourseEditorRemovedEvent
from nti.contenttypes.courses.interfaces import CourseInstructorAddedEvent
from nti.contenttypes.courses.interfaces import CourseInstructorRemovedEvent

from nti.contenttypes.courses.sharing import add_principal_to_course_content_roles
from nti.contenttypes.courses.sharing import remove_principal_from_course_content_roles

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_instructors
from nti.contenttypes.courses.utils import deny_instructor_access_to_course
from nti.contenttypes.courses.utils import grant_instructor_access_to_course

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_INSTRUCTORS,
             request_method='GET',
             permission=nauth.ACT_NTI_ADMIN)
class CourseInstructorsView(AbstractAuthenticatedView):
    """
    Fetch all instructors for the given course.
    """

    def __call__(self):
        instructors = get_course_instructors(self.context)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = len(instructors)
        result[ITEMS] = [User.get_user(x) for x in instructors]
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_EDITORS,
             request_method='GET',
             permission=nauth.ACT_NTI_ADMIN)
class CourseEditorsView(AbstractAuthenticatedView):
    """
    Fetch all editors for the given course.
    """

    def __call__(self):
        editors = get_course_editors(self.context)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = len(editors)
        result[ITEMS] = [IUser(x) for x in editors]
        return result


class AbstractRoleManagerView(AbstractAuthenticatedView,
                              ModeledContentUploadRequestUtilsMixin):
    """
    A base class for granting/denying user permissions to a course.
    """

    def _edit_permissions(self, user):
        """
        Alters permission on the course for the given user.
        """
        raise NotImplementedError()

    def readInput(self):
        if self.request.body:
            values = read_body_as_external_object(self.request)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _get_users(self):
        values = self.readInput()
        result =   values.get('name') \
                or values.get('user') \
                or values.get('users')
        if not result:
            raise_error({
                    u'message': _("No users given."),
                    u'code': 'NoUsersGiven.',
                })
        result = result.split(',')
        return result

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    @Lazy
    def entry_ntiid(self):
        return ICourseCatalogEntry(self.course).ntiid

    @Lazy
    def role_manager(self):
        return IPrincipalRoleManager(self.course)

    def __call__(self):
        usernames = self._get_users()
        for username in usernames:
            user = User.get_user(username)
            if user is None:
                raise_error({
                    u'message': _("User does not exist."),
                    u'code': 'UserDoesNotExist',
                })
            self._edit_permissions(user)
            notify(self.EVENT_FACTORY(user, self.course))
        return hexc.HTTPNoContent()


class AbstractCourseGrantView(AbstractRoleManagerView):

    def grant_permission(self, user):
        principal_id = IPrincipal(user).id
        self.role_manager.assignRoleToPrincipal(self.ROLE_ID, principal_id)
        logger.info('Granted user access to course (%s) (%s) (%s)',
                    user.username, self.ROLE_ID, self.entry_ntiid)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_INSTRUCTORS,
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN)
class CourseInstructorsInsertView(AbstractCourseGrantView):
    """
    Insert new instructors for the given course. We do not accept
    TAs at this point.
    """

    ROLE_ID = RID_INSTRUCTOR
    EVENT_FACTORY = CourseInstructorAddedEvent

    def grant_permission(self, user):
        super(CourseInstructorsInsertView, self).grant_permission(user)
        prin = IPrincipal(user)
        # Idempotent
        if prin not in self.course.instructors:
            self.course.instructors += (prin,)
        grant_instructor_access_to_course(user, self.course)
    _edit_permissions = grant_permission


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_EDITORS,
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN)
class CourseEditorsInsertView(AbstractCourseGrantView):
    """
    Insert new editors for the given course.
    """

    ROLE_ID = RID_CONTENT_EDITOR
    EVENT_FACTORY = CourseEditorAddedEvent

    def grant_permission(self, user):
        super(CourseEditorsInsertView, self).grant_permission(user)
        add_principal_to_course_content_roles(user, self.course)
    _edit_permissions = grant_permission


class AbstractCourseDenyView(AbstractRoleManagerView):

    def deny_permission(self, user):
        principal_id = IPrincipal(user).id
        # Matches what we do during sync.
        self.role_manager.unsetRoleForPrincipal(self.ROLE_ID, principal_id)
        logger.info('Removed user access to course (%s) (%s) (%s)',
                    user.username, self.ROLE_ID, self.entry_ntiid)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_REMOVE_INSTRUCTORS,
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN)
class CourseInstructorsRemovalView(AbstractCourseDenyView):
    """
    Remove instructor(s) for the given course.
    """

    ROLE_ID = RID_INSTRUCTOR
    EVENT_FACTORY = CourseInstructorRemovedEvent

    def deny_permission(self, user):
        super(CourseInstructorsRemovalView, self).deny_permission(user)
        to_remove = IPrincipal(user)
        instructors = self.course.instructors
        self.course.instructors = tuple(x for x in instructors if x != to_remove)
        deny_instructor_access_to_course(user, self.course)
    _edit_permissions = deny_permission


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_REMOVE_EDITORS,
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN)
class CourseEditorsRemovalView(AbstractCourseDenyView):
    """
    Remove editor(s) for the given course.
    """

    ROLE_ID = RID_CONTENT_EDITOR
    EVENT_FACTORY = CourseEditorRemovedEvent

    def deny_permission(self, user):
        super(CourseEditorsRemovalView, self).deny_permission(user)
        remove_principal_from_course_content_roles(user, self.course)
    _edit_permissions = deny_permission
