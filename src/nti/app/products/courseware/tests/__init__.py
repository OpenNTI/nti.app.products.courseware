#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import os
import os.path

from zope import component

import ZODB

from zope.component.interfaces import IComponents

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import users

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.app.testing.application_webtest import ApplicationTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import mock_db_trans

def publish_ou_course_entries():
	lib = component.getUtility(IContentPackageLibrary)
	try:
		del lib.contentPackages
	except AttributeError:
		pass

	lib.syncContentPackages()

def _do_then_enumerate_library(do, sync_libs=False):

	database = ZODB.DB( ApplicationTestLayer._storage_base,
						database_name='Users')
	@WithMockDS(database=database)
	def _create():
		with mock_db_trans():
			do()
			publish_ou_course_entries()
			if sync_libs:
				from nti.app.contentlibrary.admin_views import _SyncAllLibrariesView
				view = _SyncAllLibrariesView(None)
				view._SLEEP = False # see comments in the view class
				view()
	_create()

def _reset_site_libs():
	seen = []

	def d():
		lib = component.getUtility(IContentPackageLibrary)
		if lib in seen:
			return
		seen.append(lib)
		lib.resetContentPackages()

	from zope.component import hooks
	with hooks.site(None):
		d()
	run_job_in_all_host_sites(d)

class LegacyInstructedCourseApplicationTestLayer(ApplicationTestLayer):

	_library_path = 'Library'

	@staticmethod
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
		component.provideUtility(cls._setup_library(cls), IContentPackageLibrary)

		_do_then_enumerate_library(lambda: users.User.create_user( username='harp4162', password='temp001') )

		database = ZODB.DB( ApplicationTestLayer._storage_base,
							database_name='Users')
		@WithMockDS(database=database)
		def _drop_any_direct_catalog_references():
			with mock_db_trans(site_name='platform.ou.edu'):
				# make sure they get looked up through the catalog
				cat = component.getUtility(ICourseCatalog)
				for i in cat.iterCatalogEntries():
					course = ICourseInstance(i)
					assert course.legacy_catalog_entry is not None
					del course._v_catalog_entry

		_drop_any_direct_catalog_references()


	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered
		def cleanup():
			_reset_site_libs()
			cls.__old_library.resetContentPackages()
			component.provideUtility(cls.__old_library, IContentPackageLibrary)
			users.User.delete_user('harp4162')
			component.getGlobalSiteManager().getUtility(ICourseCatalog).clear()
			component.getUtility(IComponents,name='platform.ou.edu').getUtility(ICourseCatalog).clear()

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

class RestrictedInstructedCourseApplicationTestLayer(ApplicationTestLayer):

	_library_path = 'RestrictedLibrary'

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(LegacyInstructedCourseApplicationTestLayer._setup_library(cls), IContentPackageLibrary)

		_do_then_enumerate_library(lambda: users.User.create_user( username='harp4162', password='temp001') )

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered
		def cleanup():
			_reset_site_libs()
			cls.__old_library.resetContentPackages()
			component.provideUtility(cls.__old_library, IContentPackageLibrary)
			users.User.delete_user('harp4162')
			component.getGlobalSiteManager().getUtility(ICourseCatalog).clear()
			component.getUtility(IComponents,name='platform.ou.edu').getUtility(ICourseCatalog).clear()

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

class PersistentInstructedCourseApplicationTestLayer(ApplicationTestLayer):
	# A mix of new and old-style courses

	_library_path = 'PersistentLibrary'

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(LegacyInstructedCourseApplicationTestLayer._setup_library(cls), IContentPackageLibrary)
		_do_then_enumerate_library(lambda: users.User.create_user( username='harp4162', password='temp001'),
								   sync_libs=True)

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered

		def cleanup():
			_reset_site_libs()
			cls.__old_library.resetContentPackages()

			component.provideUtility(cls.__old_library, IContentPackageLibrary)
			users.User.delete_user('harp4162')
			component.getGlobalSiteManager().getUtility(ICourseCatalog).clear()
			component.getUtility(IComponents,name='platform.ou.edu').getUtility(ICourseCatalog).clear()

			from nti.site.site import get_site_for_site_names
			site = get_site_for_site_names(('platform.ou.edu',))
			cc = site.getSiteManager().getUtility(ICourseCatalog)
			for x in list(cc):
				del cc[x]

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

# Export the new-style stuff as default
InstructedCourseApplicationTestLayer = PersistentInstructedCourseApplicationTestLayer
