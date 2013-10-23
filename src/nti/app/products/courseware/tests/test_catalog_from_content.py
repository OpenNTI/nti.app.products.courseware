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
from hamcrest import has_key
from hamcrest import has_entry

from nti.testing import base
from nti.testing import matchers

import os
from zope import component

from nti.app.testing.application_webtest import SharedApplicationTestBase

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import StaticFilesystemLibrary

class TestApplicationCatalogFromContent(SharedApplicationTestBase):

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		return StaticFilesystemLibrary(
					paths=(os.path.join(
						os.path.dirname(__file__),
						'Library',
						'IntroWater'), ))

	def test_content(self):
		"basic test to be sure we got the content we need"

		lib = component.getUtility(IContentPackageLibrary)

		assert_that( lib.pathToNTIID('tag:nextthought.com,2011-10:OU-HTML-ENGR1510_Intro_to_Water.engr_1510_901_introduction_to_water'),
					 is_not( none() ) )
