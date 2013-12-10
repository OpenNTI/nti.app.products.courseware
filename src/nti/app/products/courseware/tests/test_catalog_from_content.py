#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from hamcrest import not_none
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import has_items
from hamcrest import has_item
from hamcrest import has_property

from nti.testing import base
from nti.testing import matchers
from nti.testing.matchers import verifiably_provides, validly_provides

import os
from zope import component

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.dataserver.tests import mock_dataserver

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library


from ..interfaces import ICourseCatalog
from ..interfaces import ICourseCatalogLegacyEntry
from ..interfaces import ICourseCatalogInstructorLegacyInfo
from ..interfaces import ILegacyCommunityBasedCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.tests import externalizes
from nti.dataserver.authorization_acl import ACL


class TestApplicationCatalogFromContent(SharedApplicationTestBase):

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		return Library(
					paths=(os.path.join(
									os.path.dirname(__file__),
									'Library',
									'IntroWater'),
						   os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice')
				   ))

	@WithSharedApplicationMockDS(users='harp4162')
	def test_content(self):
		"basic test to be sure we got the content we need"

		lib = component.getUtility(IContentPackageLibrary)
		# Now that we have created the instructor user, we need to re-enumerate
		# the library so it gets noticed
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			catalog = component.getUtility(ICourseCatalog)
			del catalog._entries[:] # XXX

			getattr(lib, 'contentPackages')

		# This one has a <info> tag
		assert_that( lib.pathToNTIID('tag:nextthought.com,2011-10:OU-HTML-ENGR1510_Intro_to_Water.engr_1510_901_introduction_to_water'),
					 is_not( none() ) )
		# This one just has the file, which is simplified as an already running
		# course.
		assert_that( lib.pathToNTIID("tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice"),
					 is_not( none() ) )

		catalog = component.getUtility( ICourseCatalog )
		# Both get picked up
		assert_that( catalog, has_length( 2 ) )
		assert_that( catalog, has_items( verifiably_provides(ICourseCatalogLegacyEntry),
										 verifiably_provides(ICourseCatalogLegacyEntry) ))
		water = catalog[0] if catalog[0].Title == 'Introduction to Water' else catalog[1]
		assert_that( water.Instructors, has_items( verifiably_provides(ICourseCatalogInstructorLegacyInfo),
												   verifiably_provides(ICourseCatalogInstructorLegacyInfo)))
		assert_that( water.Instructors, has_items( has_property('username', 'saba1234'),
												   has_property('username', 'cham1234') ) )

		assert_that( catalog,
					 has_items(
							 has_properties( 'ProviderUniqueID', 'ENGR 1510-901',
											 'Title', 'Introduction to Water',
											 'Communities', ['ENGR1510.ou.nextthought.com'],
											 'LegacyPurchasableIcon', '/IntroWater/images/ENGR1510_promo.png'),
							 has_properties( 'ProviderUniqueID', 'CLC 3403',
											 'Title', 'Law and Justice',
											 'Communities', ['CLC3403.ou.nextthought.com'] ) ) )

		# Externalization
		with mock_dataserver.mock_db_trans(self.ds):
			assert_that( list(catalog), has_items(
				externalizes( has_entry('Class', 'CourseCatalogLegacyEntry')),
				externalizes( has_entries(
					'MimeType', 'application/vnd.nextthought.courseware.coursecataloglegacyentry',
					'Duration', 'P112D',
					'StartDate', '2014-01-13',
					'LegacyPurchasableIcon', '/IntroWater/images/ENGR1510_promo.png'))))

		# These content units can be adapted to course instances
		with mock_dataserver.mock_db_trans(self.ds):
			for package in lib.contentPackages:
				inst = ICourseInstance(package)
				assert_that( inst, validly_provides(ILegacyCommunityBasedCourseInstance))
				assert_that( inst, externalizes( has_entries( 'Class', 'LegacyCommunityBasedCourseInstance',
															  'MimeType', 'application/vnd.nextthought.courses.legacycommunitybasedcourseinstance',
															  'LegacyInstructorForums', not_none(),
															  'LegacyScopes', has_entries('restricted', not_none(),
																						  'public', not_none() ) ) ) )

				acl = ACL(inst, None)
				assert_that( acl, is_( not_none() ))

				if 'LawAndJustice' in package.ntiid:
					assert_that( inst.instructors, has_length( 1 ))
					assert_that( acl, has_item(has_item(inst.instructors[0])))
					assert_that( inst.Outline, has_length(6))
					assert_that( inst.Outline["0"], has_property('title', 'Introduction'))
					assert_that( inst.Outline["0"]["0"].AvailableBeginning, is_(not_none()))
					assert_that( inst.Outline["0"]["0"].AvailableEnding, is_(not_none()))
					assert_that( inst.Outline["0"]["0"], externalizes(has_entry('AvailableEnding',
																				'2013-08-22T04:59:59Z')))
