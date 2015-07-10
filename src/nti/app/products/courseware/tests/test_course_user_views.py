#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from zope import component

from nti.app.products.courseware.interfaces import IClassmatesSuggestedContactsProvider

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE

from nti.dataserver.users import User

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestCourseUserViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_classmates(self):
		enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
		course_href = None

		non_student = 'billbob'
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user(non_student)

		students = ("Ichigo", "Inoue", "Keigo", "Ishida")
		for student in students:
			with mock_dataserver.mock_db_trans(self.ds):
				self._create_user(student)

		captains = ('Zaraki', 'Hirako' )
		for captain in captains:
			with mock_dataserver.mock_db_trans(self.ds):
				self._create_user(captain)

		degree_captains = ('Ukitake', 'Kyoraku' )
		for captain in degree_captains:
			with mock_dataserver.mock_db_trans(self.ds):
				self._create_user(captain)

		for student in students:
			data = {'username':student, 'ntiid': self.course_ntiid, 'scope':ES_PUBLIC}
			res = self.testapp.post_json( enroll_url, data )
			if not course_href:
				course_href = res.json_body['CourseInstance']['href']

		for captain in captains:
			with mock_dataserver.mock_db_trans(self.ds):
				data = {'username':captain, 'ntiid': self.course_ntiid, 'scope':ES_CREDIT}
				self.testapp.post_json( enroll_url, data )

		for captain in degree_captains:
			with mock_dataserver.mock_db_trans(self.ds):
				data = {'username':captain, 'ntiid': self.course_ntiid, 'scope':ES_CREDIT_DEGREE}
				self.testapp.post_json( enroll_url, data )

		provider = component.queryUtility(IClassmatesSuggestedContactsProvider)
		assert_that(provider, is_not(none()))

		classmates_href = course_href + '/Classmates'

		environ = self._make_extra_environ(username=non_student)
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(classmates_href, extra_environ=environ, status=403 )

		environ = self._make_extra_environ(username='ichigo')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(classmates_href, extra_environ=environ, status=200 )
		assert_that(res.json_body,
					has_entry( 'Items', has_length(3) ))

		environ = self._make_extra_environ(username='hirako')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(classmates_href, extra_environ=environ, status=200 )
		assert_that(res.json_body,
					has_entry( 'Items', has_length(5) ))

		environ = self._make_extra_environ(username='ukitake')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(classmates_href, extra_environ=environ, status=200 )
		assert_that(res.json_body,
					has_entry( 'Items', has_length(7) ))

		with mock_dataserver.mock_db_trans(self.ds,  site_name='platform.ou.edu'):
			# Regular user
			ichigo = User.get_user('ichigo')
			suggestions = provider.suggestions(ichigo)
			assert_that(suggestions, has_length(3))

			# Multi-user, non-classmates
			source_user = User.get_user( non_student )
			suggestions = provider.suggestions(ichigo, source_user=source_user )
			assert_that(suggestions, has_length(0))

			# Multi-user, classmates
			source_user = User.get_user( "Keigo" )
			suggestions = provider.suggestions(ichigo, source_user=source_user )
			assert_that(suggestions, has_length(3))

		user_classmates_url = '/dataserver2/users/ichigo/Classmates'
		environ = self._make_extra_environ(username='ichigo')
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(user_classmates_url, extra_environ=environ, status=200 )
		assert_that(res.json_body,
					has_entry( 'Items', has_length(3) ))

		user_classmates_url = '/dataserver2/users/%s/Classmates' % non_student
		environ = self._make_extra_environ(username=non_student)
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
		res = self.testapp.get(user_classmates_url, extra_environ=environ, status=200 )
		assert_that(res.json_body,
					has_entry( 'Items', has_length(0) ))
