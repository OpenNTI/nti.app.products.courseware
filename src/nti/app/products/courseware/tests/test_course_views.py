#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import contains
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import contains_inanyorder

from zope import component

from zope.annotation.interfaces import IAnnotations

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseTabPreferences


from nti.dataserver.users.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestCourseEnrollmentRosterGetView(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = 'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	roster_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice/CourseEnrollmentRoster'

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_enrollment_roster(self):
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user(u'marco')
			self._create_user(u'alana')

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			marco = User.get_user('marco')
			alana = User.get_user('alana')

			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)

			enrollment_manager = ICourseEnrollmentManager(course)
			enrollment_manager.enroll(marco)
			enrollment_manager.enroll(alana, scope=ES_CREDIT)

		result = self.testapp.get(self.roster_url)
		result = result.json_body

		assert_that(result, has_entries({'Items': has_length(2),
										 'ItemCount': 2,
										 'TotalItemCount': 2}))
		assert_that(result['Items'][0]['LastSeenTime'], not_none())


class TestCourseTabPreferencesView(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = 'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	course_url = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/Fall2013/CLC3403_LawAndJustice'

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_update_and_read(self):
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			assert_that('CourseTabPreferences' in IAnnotations(course), is_(False))

		# empty read
		url = self.course_url + "/CourseTabPreferences"
		result = self.testapp.get(url, status=200)
		assert_that(result.json_body, has_entries({'names': has_length(0),
												   'order': has_length(0)}))

		# bad request
		self.testapp.put_json(url, status=400)

		# update
		params = { "names": {"1":"a", "2": "b"} }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b"}),
												   'order': has_length(0)}))

		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			assert_that('CourseTabPreferences' in IAnnotations(course), is_(True))
			prefs = ICourseTabPreferences(course)
			assert_that(prefs._names, has_entries({"1": "a", "2": "b"}))
			assert_that(prefs._order, has_length(0))

		params = { "names": {"3": "c"} }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"3": "c"}),
												   'order': has_length(0)}))

		params = { "names": None }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_length(0),
												   'order': has_length(0)}))

		params = { "names": {} }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_length(0),
												  'order': has_length(0)}))

		params = { "names": "abc" }
		result = self.testapp.put_json(url, params=params, status=422)

		# order
		params = { "names": {"1":"a", "2": "b", "3": "c"} , "order": ["1", "2", "3"] }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("1", "2", "3")}))

		params = { "order": ["2", "1", "3"] }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("2", "1", "3")}))

		params = { "order": ["2", "1"] }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("2", "1")}))

		params = { "order": ["2", "1", "3", "4"] }
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("2", "1", "3", "4")}))

		params = { "order": "213" }
		result = self.testapp.put_json(url, params=params, status=422)

		# read
		result = self.testapp.get(url, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("2", "1", "3", "4")}))

		# section courses
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			tab_pref = ICourseTabPreferences(course.SubInstances['01'])
			assert_that(tab_pref.names, has_entries({"1": "a", "2": "b", "3": "c"}))
			assert_that(tab_pref.order, contains("2", "1", "3", "4"))

		url = self.course_url + "/SubInstances/01/CourseTabPreferences"
		result = self.testapp.get(url, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("2", "1", "3", "4")}))

		params = { "names": {"1":"aa", "2": "b", "4": "z"}, "order": ["4", "3", "2"]}
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "aa", "2": "b", "4": "z"}),
												   'order': contains("4", "3", "2")}))

		# clear section, inherit from parent
		params = { "names": None, "order": None}
		result = self.testapp.put_json(url, params=params, status=200)
		assert_that(result.json_body, has_entries({'names': has_entries({"1": "a", "2": "b", "3": "c"}),
												   'order': contains("2", "1", "3", "4")}))

		# clear parent
		with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			pref = ICourseTabPreferences(course)
			pref.clear()

		result = self.testapp.get(url, status=200)
		assert_that(result.json_body, has_entries({'names': has_length(0),
												   'order': has_length(0)}))
