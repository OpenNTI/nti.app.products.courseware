#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import assert_that
does_not = is_not

from zope import component

from zope.intid import IIntIds

from nti.app.notabledata.interfaces import IUserPriorityCreatorNotableProvider

from nti.app.products.courseware.notables import TopLevelPriorityNotableFilter

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.contenttypes.note import Note

from nti.dataserver.users import User
from nti.dataserver.users.communities import Community

from nti.dataserver.tests import mock_dataserver

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

class TestNotables(ApplicationLayerTest):
	layer = PersistentInstructedCourseApplicationTestLayer

	@WithSharedApplicationMockDS(users=True, testapp=True)
	def test_priority_user_notables(self):

		# Enroll in our course, create two notes: one visible to my class
		# and one only through my community.  Only the one visible to my
		# course is notable.
		with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
			user = User.get_user('sjohnson@nextthought.com')

			cat = component.getUtility(ICourseCatalog)

			parent_course = cat['Fall2013']['CLC3403_LawAndJustice']
			course = parent_course.SubInstances['02-Restricted']
			course.instructors = parent_course.instructors
			instructor_user = parent_course.instructors[0].username
			instructor_user = User.get_user(instructor_user)

			manager = ICourseEnrollmentManager(course)
			manager.enroll(user, scope='ForCreditDegree')

			course_scope = course.SharingScopes['ForCreditDegree']
			new_community = Community.create_community(username='new_shared_community')
			new_community._note_member(user)
			# Create a note visible to my community and my course
			note1 = Note()
			note1.body = ('test222',)
			note1.creator = instructor_user
			note1.containerId = 'tag:nti:foo'
			note1.addSharingTarget(course_scope)
			note1.addSharingTarget(new_community)
			instructor_user.addContainedObject(note1)

			# Create a note visible to my community
			note2 = Note()
			note2.body = ('test222',)
			note2.creator = instructor_user
			note2.containerId = 'tag:nti:foo'
			note2.addSharingTarget(new_community)
			instructor_user.addContainedObject(note2)
			intids = component.getUtility(IIntIds)
			notable_intid = intids.getId(note1)

			notable_intids = set()
			# Intid provider
			for provider in component.subscribers((user, user),
											   IUserPriorityCreatorNotableProvider):
				notable_intids.update(provider.get_notable_intids())

			assert_that(notable_intids, contains(notable_intid))

			# Notable filter
			notable_filter = TopLevelPriorityNotableFilter(user)
			assert_that(notable_filter.is_notable(note1, user), is_(True))
			assert_that(notable_filter.is_notable(note2, user), is_(False))

			# Not for instructor
			assert_that(notable_filter.is_notable(note1, instructor_user), is_(False))
			assert_that(notable_filter.is_notable(note2, instructor_user), is_(False))
