#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid.interfaces import IIntIds

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.completion.interfaces import ICompletionContextCohort
from nti.app.contenttypes.completion.interfaces import ICompletionContextACLProvider

from nti.contenttypes.completion.authorization import ACT_VIEW_PROGRESS
from nti.contenttypes.completion.authorization import ACT_LIST_PROGRESS

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.completion.adapters import CompletableItemContainerFactory

from nti.contenttypes.completion.interfaces import ICompletionContext
from nti.contenttypes.completion.interfaces import ICompletableItemContainer

from nti.dataserver import authorization

from nti.dataserver.authorization_acl import ace_denying
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import EVERYONE_GROUP_NAME

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IPrincipal

from nti.dataserver.users.users import User

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICompletionContext)
def _course_from_completable_item(item):
    """
    Find a :class:`ICourseInstance` from the given :class:`ICompletableItem`.
    """
    course = None
    # We would always prefer to get this off of calling context
    request = get_current_request()
    if request is not None:
        course = ICourseInstance(request, None)
    if course is None:
        # Otherwise, item/user might be a best guess
        user = get_remote_user(request)
        if user is not None:
            course = component.queryMultiAdapter((item, user),
                                                 ICourseInstance)
    if course is None:
        # Or we blindly guess on and item that may be shared across
        # multiple courses
        course = ICourseInstance(item, None)
    return course


@interface.implementer(ICompletionContextACLProvider)
class CourseCompletedItemsACLProvider(object):

    def __init__(self, course, subcontext):
        self.course = course
        self.subcontext = subcontext

    @property
    def __acl__(self):
        # Admins and instructors have read and list
        aces = [ace_allowing(authorization.ROLE_ADMIN, ACT_VIEW_PROGRESS, type(self)),
                ace_allowing(authorization.ROLE_ADMIN, ACT_LIST_PROGRESS, type(self))]

        for i in self.course.instructors:
            aces.append(ace_allowing(i, ACT_VIEW_PROGRESS, type(self)))
            aces.append(ace_allowing(i, ACT_LIST_PROGRESS, type(self)))

        # If our context adapts to a user only that user can read and list.  All others
        # get explicitly denied
        user = IUser(self.subcontext, None)
        if user is not None:
            aces.append(ace_allowing(user, ACT_VIEW_PROGRESS, type(self)))
            aces.append(ace_allowing(user, ACT_LIST_PROGRESS, type(self)))
            aces.append(ace_denying(EVERYONE_GROUP_NAME,
                                    ACT_VIEW_PROGRESS, type(self)))
            aces.append(ace_denying(EVERYONE_GROUP_NAME,
                                    ACT_LIST_PROGRESS, type(self)))
        else:  # Otherwise all enrolled users have read
            sharing_scopes = self.course.SharingScopes
            sharing_scopes.initScopes()
            public_scope = sharing_scopes[ES_PUBLIC]
            aces.append(ace_allowing(IPrincipal(public_scope),
                                     ACT_VIEW_PROGRESS,
                                     type(self)))

        return acl_from_aces(aces)


@interface.implementer(ICompletionContextCohort)
class CourseStudentCohort(object):

    def __init__(self, course, scope=ES_PUBLIC):
        self.course = course
        self.scope = scope

    @Lazy
    def entities(self):
        sharing_scopes = self.course.SharingScopes
        sharing_scopes.initScopes()
        return sharing_scopes[self.scope]

    @Lazy
    def instructors(self):
        return {User.get_user(inst.id) for inst in self.course.instructors or ()}

    def __iter__(self):
        # pylint: disable=not-an-iterable,unsupported-membership-test
        inst_entities = self.instructors
        for entity in self.entities:
            if entity not in inst_entities:
                yield entity

    def iter_usernames(self):
        # pylint: disable=not-an-iterable,no-member
        inst_usernames = {inst.username for inst in self.instructors}
        for username in self.entities.iter_usernames:
            if username not in inst_usernames:
                yield username

    def iter_intids(self):
        # pylint: disable=not-an-iterable,no-member
        intids = component.getUtility(IIntIds)
        inst_intids = {intids.getId(inst) for inst in self.instructors}
        for intid in self.entities.iter_intids:
            if intid not in inst_intids:
                yield intid

    def __contains__(self, entity):
        # pylint: disable=unsupported-membership-test
        if entity in self.instructors:
            return False
        return entity in self.entities


# catalog


@interface.implementer(ICompletableItemContainer)
class SubinstanceCompletableItemContainer(object):
    """
    We want the child section course to able to override the parent course when
    definining required/optional. We currently *cannot* make an item defined as
    required/optional in the parent revert to a default state through this
    subinstance API.
    """

    def __init__(self, subinstance_container, parent_container):
        self.subinstance_container = subinstance_container
        self.parent_container = parent_container

    def get_required_keys(self):
        child = set(self.subinstance_container.get_required_keys())
        parent = set(self.parent_container.get_required_keys())
        return tuple(child | parent)

    def add_required_item(self, item):
        """
        Add a :class:`ICompletableItem` to this context as a required item.
        """
        self.subinstance_container.add_required_item(item)

    def remove_required_item(self, item):
        """
        Remove a :class:`ICompletableItem` as a required item.
        """
        self.subinstance_container.remove_required_item(item)

    def get_optional_keys(self):
        child = set(self.subinstance_container.get_optional_keys())
        parent = set(self.parent_container.get_optional_keys())
        return tuple(child | parent)

    def add_optional_item(self, item):
        """
        Add a :class:`ICompletableItem` to this context as not required.
        """
        self.subinstance_container.add_optional_item(item)

    def remove_optional_item(self, item):
        """
        Remove a :class:`ICompletableItem` as an optional item.
        """
        self.subinstance_container.remove_optional_item(item)

    def is_item_required(self, item):
        """
        Returns a bool if the given :class:`ICompletableItem` is required.
        """
        return self.subinstance_container.is_item_required(item) \
            or (    not self.subinstance_container.is_item_optional(item) \
                and self.parent_container.is_item_required(item))

    def get_required_item_count(self):
        """
        Return the count of required items.
        """
        return len(self.get_required_keys())

    def is_item_optional(self, item):
        """
        Returns a bool if the given :class:`ICompletableItem` is optional.
        """
        return self.subinstance_container.is_item_optional(item) \
            or (    not self.subinstance_container.is_item_required(item) \
                and self.parent_container.is_item_optional(item))

    def get_optional_item_count(self):
        """
        Return the count of optional items.
        """
        return len(self.get_optional_keys())

    def clear(self):
        pass


@component.adapter(ICourseSubInstance)
@interface.implementer(ICompletableItemContainer)
def section_to_container(course):
    """
    If we share an outline with our parent course, use a composite
    completable item container.
    """
    # Manually create container
    section_container = CompletableItemContainerFactory(course)
    parent_course = get_parent_course(course)
    if parent_course.Outline != course.Outline:
        return section_container
    parent_container = ICompletableItemContainer(parent_course)
    return SubinstanceCompletableItemContainer(section_container,
                                               parent_container)
