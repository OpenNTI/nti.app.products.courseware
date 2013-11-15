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
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import has_items
from hamcrest import has_property

from nti.testing import base
from nti.testing import matchers
from nti.testing.matchers import verifiably_provides

import os
from zope import component

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.dataserver.tests import mock_dataserver

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from .. import legacy
from ..interfaces import ICourseCatalog
from ..interfaces import ICourseCatalogLegacyEntry
from ..interfaces import ICourseCatalogInstructorLegacyInfo

from nti.externalization.tests import externalizes

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

	@WithSharedApplicationMockDS
	def test_content(self):
		"basic test to be sure we got the content we need"

		lib = component.getUtility(IContentPackageLibrary)

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
