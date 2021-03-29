#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_item
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from nti.testing.matchers import is_true
from nti.testing.matchers import is_false

from zope import component

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.notabledata.interfaces import IUserNotableProvider
from nti.app.notabledata.interfaces import IUserNotableSharedWithIDProvider

from nti.app.products.courseware.notables import TopLevelPriorityNotableFilter

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.authorization_utils import zope_interaction

from nti.dataserver.contenttypes.note import Note

from nti.dataserver.users.users import User

from nti.dataserver.users.communities import Community

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestNotables(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_shared_with_site_admins(self):
        """
        Notes shared to a course sharing scope are visible to a site admin.
        """
        site_admin_username = u'site_admin_notableuser001'
        with mock_dataserver.mock_db_trans():
            self._create_user(u'sjohnson@nti.com')
            self._create_user(site_admin_username)

        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            srm = IPrincipalRoleManager(getSite(), None)
            srm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, site_admin_username)

            cat = component.getUtility(ICourseCatalog)

            parent_course = cat['Fall2013']['CLC3403_LawAndJustice']
            course = parent_course.SubInstances['02-Restricted']
            course.instructors = parent_course.instructors
            instructor_user = parent_course.instructors[0].username
            instructor_user = User.get_user(instructor_user)

            course_scope = course.SharingScopes['ForCreditDegree']
            username = u'new_shared_community'
            new_community = Community.create_community(username=username)
            # Create a note visible to my community and my course
            note1 = Note()
            note1.body = (u'test222',)
            note1.creator = instructor_user
            note1.containerId = u'tag:nti:foo'
            note1.addSharingTarget(course_scope)
            note1.addSharingTarget(new_community)
            instructor_user.addContainedObject(note1)

            # Create a note visible to my community
            note2 = Note()
            note2.body = (u'test222',)
            note2.creator = instructor_user
            note2.containerId = u'tag:nti:foo'
            note2.addSharingTarget(new_community)
            instructor_user.addContainedObject(note2)

            # Site admin can see note shared with course sharing scope
            with zope_interaction(site_admin_username):
                note1_read = has_permission(ACT_READ, note1, site_admin_username)
                note2_read = has_permission(ACT_READ, note2, site_admin_username)
                assert_that(note1_read, is_true())
                assert_that(note2_read, is_false())

    @WithSharedApplicationMockDS(users=True, testapp=True)
    def test_priority_user_notables(self):
        # Enroll in our course, create two notes: one visible to my class
        # and one only through my community.  Only the one visible to my
        # course is notable.
        with mock_dataserver.mock_db_trans():
            self._create_user(u'sjohnson@nti.com')

        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            user = User.get_user(u'sjohnson@nti.com')
            cat = component.getUtility(ICourseCatalog)

            parent_course = cat['Fall2013']['CLC3403_LawAndJustice']
            course = parent_course.SubInstances['02-Restricted']
            course.instructors = parent_course.instructors
            instructor_user = parent_course.instructors[0].username
            instructor_user = User.get_user(instructor_user)

            manager = ICourseEnrollmentManager(course)
            manager.enroll(user, scope='ForCreditDegree')

            course_scope = course.SharingScopes['ForCreditDegree']
            username = u'new_shared_community'
            new_community = Community.create_community(username=username)
            new_community._note_member(user)
            # Create a note visible to my community and my course
            note1 = Note()
            note1.body = (u'test222',)
            note1.creator = instructor_user
            note1.containerId = u'tag:nti:foo'
            note1.addSharingTarget(course_scope)
            note1.addSharingTarget(new_community)
            instructor_user.addContainedObject(note1)

            # Create a note visible to my community
            note2 = Note()
            note2.body = (u'test222',)
            note2.creator = instructor_user
            note2.containerId = u'tag:nti:foo'
            note2.addSharingTarget(new_community)
            instructor_user.addContainedObject(note2)
            intids = component.getUtility(IIntIds)
            notable_intid = intids.getId(note1)

            notable_intids = set()
            # Intid provider
            for provider in component.subscribers((user, user),
                                                  IUserNotableProvider):
                notable_intids.update(provider.get_notable_intids())

            assert_that(notable_intids, contains(notable_intid))

            # Notable filter
            notable_filter = TopLevelPriorityNotableFilter(user)
            assert_that(notable_filter.is_notable(note1, user), is_(True))
            assert_that(notable_filter.is_notable(note2, user), is_(False))

            # Not for instructor
            assert_that(notable_filter.is_notable(note1, instructor_user),
                        is_(False))
            assert_that(notable_filter.is_notable(note2, instructor_user),
                        is_(False))

            # Shared with ntiids
            shared_with_ids = set()
            for provider in component.subscribers((user, user),
                                                  IUserNotableSharedWithIDProvider):
                shared_with_ids.update(provider.get_shared_with_ids())
            assert_that(shared_with_ids, has_item(course_scope.NTIID))

            # Validate preview mode hides notables
            entry = ICourseCatalogEntry(course)
            entry.Preview = True

            notable_intids = set()
            for provider in component.subscribers((user, user),
                                                  IUserNotableProvider):
                notable_intids.update(provider.get_notable_intids())

            assert_that(notable_intids, has_length(0))
            assert_that(notable_filter.is_notable(note1, user), is_(False))

            # Shared with ntiids should be empty now that course is in preview
            shared_with_ids = set()
            for provider in component.subscribers((user, user),
                                                  IUserNotableSharedWithIDProvider):
                shared_with_ids.update(provider.get_shared_with_ids())
            assert_that(shared_with_ids, does_not(has_item(course_scope.NTIID)))
