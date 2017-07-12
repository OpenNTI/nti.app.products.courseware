#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_length

from datetime import datetime
import time

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestCatalogViews(ApplicationLayerTest):

	layer = PersistentInstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	@WithSharedApplicationMockDS(
		testapp=True, users=True, default_authenticate=False)
	def test_anonymously_available_courses_view(self):
		anonymous_instances_url = '/dataserver2/_AnonymouslyButNotPubliclyAvailableCourseInstances'

		# authed users also can't fetch this view
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user('ichigo')

		unauthed_environ = self._make_extra_environ(username='ichigo')
		self.testapp.get(
                    anonymous_instances_url,
                    extra_environ=unauthed_environ,
                    status=403)

		# unauthed requests that have our special classifier are allowed
		extra_environ = self._make_extra_environ(username=None)
		result = self.testapp.get(
                    anonymous_instances_url,
                    extra_environ=extra_environ,
                    status=200)
		result = result.json_body
		assert_that(result, has_entry('ItemCount', 1))

	@WithSharedApplicationMockDS(
		testapp=True, users=True, default_authenticate=True)
	def test_administered_paging(self):
		admin_environ = self._make_extra_environ()

		favorites_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AdministeredCourses/@@WindowedAdministered"

		notBefore = time.mktime(datetime(2012, 8, 14).timetuple())
		notAfter = time.mktime(datetime(2015, 8, 25).timetuple())

		get_params = {"notBefore": notBefore, "notAfter": notAfter}

		res = self.testapp.get(favorites_path,
                         get_params,
                         extra_environ=admin_environ,
                         status=200)
		
		

		assert_that(res.json_body, has_entry("ItemCount", 7))
		
		# If I give no parameters, then I should get everything
		res = self.testapp.get(favorites_path,
                         extra_environ=admin_environ,
                         status=200)

		assert_that(res.json_body, has_entry("ItemCount", 7))

	@WithSharedApplicationMockDS(
		testapp=True, users=True, default_authenticate=True)
	def test_enrolled_paging(self):
		admin_environ = self._make_extra_environ()
  
		enroll_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses"
		get_enrolled_courses_path = enroll_path + "/@@WindowedEnrolled"
  		
		notBefore = time.mktime(datetime(2012, 8, 14).timetuple())
		notAfter = time.mktime(datetime(2015, 8, 25).timetuple())
 
		get_params = {"notBefore": notBefore, "notAfter": notAfter}
  
		res = self.testapp.get(get_enrolled_courses_path,
                         get_params,
                         extra_environ=admin_environ,
                         status=200)
  
		assert_that(res.json_body, get_params, has_entry("Items", has_length(1)))
  
		self.testapp.post_json(enroll_path,
                         'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice',
                         status=201)
		self.testapp.post_json(enroll_path,
                         'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995',
                         status=201)
  
		res = self.testapp.get(enroll_path,
                         extra_environ=admin_environ,
                         status=200)
  
		assert_that(res.json_body, has_entry("Items", has_length(2)))
  
		res = self.testapp.get(get_enrolled_courses_path,
                         get_params,
                         extra_environ=admin_environ,
                         status=200)
  
		assert_that(res.json_body, has_entry("ItemCount", 2))
		
		# If I give just notBefore, then I should get everything after that
		notBefore = time.mktime(datetime(2014, 8, 14).timetuple())
		get_params = {"notBefore": notBefore}
  
		res = self.testapp.get(get_enrolled_courses_path,
                         get_params,
                         extra_environ=admin_environ,
                         status=200)
  
		assert_that(res.json_body, get_params, has_entry("ItemCount", 1))
		
		# Similar to notAfter
		notAfter = time.mktime(datetime(2014, 8, 25).timetuple())
		get_params = {"notAfter": notAfter}
  
		res = self.testapp.get(get_enrolled_courses_path,
                         get_params,
                         extra_environ=admin_environ,
                         status=200)
		
		assert_that(res.json_body, get_params, has_entry("ItemCount", 1))
  
	@WithSharedApplicationMockDS(
		testapp=True, users=True, default_authenticate=True)
	def test_all_paging(self):
		admin_environ = self._make_extra_environ()
  
		all_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses"
  
		res = self.testapp.get(all_path,
                         extra_environ=admin_environ)
  
		assert_that(res.json_body, has_entry("Items", has_length(8)))
  
		all_paged_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/AllCourses/@@WindowedAllCourses"
  
		notBefore = time.mktime(datetime(2012, 8, 14).timetuple())
		notAfter = time.mktime(datetime(2015, 8, 1).timetuple())
 
		get_params = {"notBefore": notBefore, "notAfter": notAfter}
  
		res = self.testapp.get(all_paged_path,
                         get_params,
                         extra_environ=admin_environ)
  
		assert_that(res.json_body, has_entry("ItemCount", 4))
  
	@WithSharedApplicationMockDS(
		testapp=True, users=True, default_authenticate=True)
	def test_bad_page_request(self):
		admin_environ = self._make_extra_environ()
  
		enroll_path = "/dataserver2/users/sjohnson%40nextthought.com/Courses/EnrolledCourses/@@WindowedEnrolled"
  
		get_params = {"notBefore": "Garbage"}
  
		# Test with not an integer
		self.testapp.get(
                    enroll_path,
                    get_params,
                    extra_environ=admin_environ,
                    status=400)
