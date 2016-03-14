#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

class TestMigrate(ApplicationLayerTest):

	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_migrate_legacy_to_new(self):
		self.testapp.post('/dataserver2/@@SyncAllLibraries')
		res = self.testapp.get('/dataserver2/CourseAdmin/LegacyCourseEnrollmentMigrator')
		assert_that(res.json_body, is_(
			[['Nothing in site', 'demo.nextthought.com'],
			 ['Nothing in site', 'labs.symmys.com'],
			 ['Nothing in site', 'law.nextthought.com'],
			 ['Nothing in site', 'mathcounts.nextthought.com'],
			 ['Nothing in site', 'personalleadership.nextthought.com'],
			 ['Fall2014/BIOL 2124',
			  'No community',
			  {'public': 'BIOL2124F2014.ou.nextthought.com', 'restricted': None}],
			 ['Fall2014/CHEM 1315',
			  'No community',
			  {'public': 'CHEM1315F2014.ou.nextthought.com',
			   'restricted': 'CHEM1315Fall2014.ou.nextthought.com'}],
			 ['Fall2014/CHEM 4970/SubInstances/100',
			  'No community',
			  {'public': 'CHEM4970F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:morv1533-MeetingRoom:Group-chem4970fall2014.ou.nextthought.com'}],
			 ['Fall2014/CLC 3403',
			  'No community',
			  {'public': 'CLC3403F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:harp4162-MeetingRoom:Group-clc3403fall2014.ou.nextthought.com'}],
			 ['Fall2014/IAS 2003',
			  'No community',
			  {'public': 'IAS2003F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:gril4990-MeetingRoom:Group-ias2003fall2014.ou.nextthought.com'}],
			 ['Fall2014/PHIL 1203',
			  'No community',
			  {'public': 'PHIL1203F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:judi5807-MeetingRoom:Group-phil1203fall2014.ou.nextthought.com'}],
			 ['Fall2014/SOC 1113',
			  'No community',
			  {'public': 'SOC1113F2014.ou.nextthought.com',
			   'restricted': 'tag:nextthought.com,2011-10:damp8528-MeetingRoom:Group-soc1113fall2014.ou.nextthought.com'}],
			 ['Fall2014/UCOL 1002',
			  'No community',
			  {'public': 'UCOL1002F2014.ou.nextthought.com', 'restricted': None}],
			 ['Nothing in site', 'prmia.nextthought.com'],
			 ['Nothing in site', 'rwanda.nextthought.com'],
			 ['Nothing in site', 'symmys-alpha.nextthought.com'],
			 ['Nothing in site', 'symmys.nextthought.com'],
			 ['Nothing in site', 'testmathcounts.nextthought.com'],
			 ['Nothing in site', 'testprmia.nextthought.com']]
		))
