#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from nti.app.testing.application_webtest import ApplicationTestLayer
import os
import os.path

import ZODB
from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import mock_db_trans

from nti.dataserver import users
from zope.component.interfaces import IComponents
from nti.app.products.courseware.interfaces import ICourseCatalog
from nti.contentlibrary.interfaces import IContentPackageLibrary

def publish_ou_course_entries():
	lib = component.getUtility(IContentPackageLibrary)
	try:
		del lib.contentPackages
	except AttributeError:
		pass

	lib.syncContentPackages()

	components = component.getUtility(IComponents, name='platform.ou.edu')
	catalog = components.getUtility( ICourseCatalog )

	# re-register globally
	global_catalog = component.getUtility(ICourseCatalog)
	for k, v in catalog.items():
		global_catalog._SampleContainer__data[k] = v

	try:
		del global_catalog._BTreeContainer__len
	except AttributeError:
		pass

def _do_then_enumerate_library(do):

	database = ZODB.DB( ApplicationTestLayer._storage_base,
						database_name='Users')
	@WithMockDS(database=database)
	def _create():
		with mock_db_trans():
			do()
			publish_ou_course_entries()

	_create()

class InstructedCourseApplicationTestLayer(ApplicationTestLayer):

	_library_path = 'Library'

	@classmethod
	def _setup_library( cls, *args, **kwargs ):
		from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library
		lib = Library(
			paths=(
				os.path.join(
					os.path.dirname(__file__),
					cls._library_path,
					'IntroWater'),
				os.path.join(
					os.path.dirname(__file__),
					cls._library_path,
					'CLC3403_LawAndJustice')) )
		return lib

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(cls._setup_library(), IContentPackageLibrary)

		_do_then_enumerate_library(lambda: users.User.create_user( username='harp4162', password='temp001') )

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered
		def cleanup():
			del component.getUtility(IContentPackageLibrary).contentPackages
			try:
				del cls.__old_library.contentPackages
			except AttributeError:
				pass
			component.provideUtility(cls.__old_library, IContentPackageLibrary)

		_do_then_enumerate_library(cleanup)
		del cls.__old_library



class RestrictedInstructedCourseApplicationTestLayer(InstructedCourseApplicationTestLayer):

	_library_path = 'RestrictedLibrary'

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(cls._setup_library(), IContentPackageLibrary)
		_do_then_enumerate_library(lambda: None)

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered
		def cleanup():
			del component.getUtility(IContentPackageLibrary).contentPackages
			try:
				del cls.__old_library.contentPackages
			except AttributeError:
				pass
			component.provideUtility(cls.__old_library, IContentPackageLibrary)

		_do_then_enumerate_library(cleanup)
		del cls.__old_library
