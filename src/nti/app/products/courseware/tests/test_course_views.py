#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property

from zope import component

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager


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
