#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import os
import os.path

from zope import component
from zope import interface

import ZODB

from zope.component.interfaces import IComponents

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import users
from nti.dataserver.users.interfaces import IRecreatableUser

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

def _delete_users(usernames=()):
	for username in usernames or ():
		users.User.delete_user(username)

def _clear_catalogs(site_names=()):
	component.getGlobalSiteManager().getUtility(ICourseCatalog).clear()
	for name in site_names or ():
		component.getUtility(IComponents,name=name).getUtility(ICourseCatalog).clear()

def _delete_catalogs(site_names=()):
	from nti.site.site import get_site_for_site_names
	for name in site_names or ():
		site = get_site_for_site_names((name,))
		cc = site.getSiteManager().getUtility(ICourseCatalog)
		for x in list(cc):
			del cc[x]

class LegacyInstructedCourseApplicationTestLayer(ApplicationTestLayer):

	_library_path = 'Library'
	_instructors = ('harp4162',)
	_sites_names = ('platform.ou.edu',)

	@classmethod
	def _user_creation(cls):
		for username in cls._instructors:
			user = users.User.create_user(username=username, password='temp001')
			interface.alsoProvides( user, IRecreatableUser )

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
		_do_then_enumerate_library(cls._user_creation)

		database = ZODB.DB(ApplicationTestLayer._storage_base, database_name='Users')

		@WithMockDS(database=database)
		def _drop_any_direct_catalog_references():
			for name in cls._sites_names:
				with mock_db_trans(site_name=name):
					## make sure they get looked up through the catalog
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
			_delete_users(cls._instructors)
			_clear_catalogs(cls._sites_names)

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

class RestrictedInstructedCourseApplicationTestLayer(ApplicationTestLayer):

	_library_path = 'RestrictedLibrary'
	_instructors = ('harp4162',)
	_sites_names = ('platform.ou.edu',)

	@classmethod
	def _user_creation(cls):
		for username in cls._instructors:
			user = users.User.create_user(username=username, password='temp001')
			interface.alsoProvides( user, IRecreatableUser )

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(LegacyInstructedCourseApplicationTestLayer._setup_library(cls),
								 IContentPackageLibrary)
		_do_then_enumerate_library(cls._user_creation )

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered
		def cleanup():
			_reset_site_libs()
			cls.__old_library.resetContentPackages()
			component.provideUtility(cls.__old_library, IContentPackageLibrary)
			_delete_users(cls._instructors)
			_clear_catalogs(cls._sites_names)

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

class NotInstructedCourseApplicationTestLayer(ApplicationTestLayer):

	_library_path = 'PersistentLibrary'
	_sites_names = ('platform.ou.edu',)

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(LegacyInstructedCourseApplicationTestLayer._setup_library(cls),
								 IContentPackageLibrary)
		_do_then_enumerate_library(lambda: lambda: True, sync_libs=True)

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered

		def cleanup():
			_reset_site_libs()
			cls.__old_library.resetContentPackages()
			component.provideUtility(cls.__old_library, IContentPackageLibrary)
			_clear_catalogs(cls._sites_names)
			_delete_catalogs(cls._sites_names)

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

class PersistentInstructedCourseApplicationTestLayer(ApplicationTestLayer):
	# A mix of new and old-style courses

	_library_path = 'PersistentLibrary'
	_instructors = ('harp4162', 'bailey.norwood@okstate.edu')
	_sites_names = ('platform.ou.edu', 'okstate.nextthought.com')

	@classmethod
	def _user_creation(cls):
		for username in cls._instructors:
			user = users.User.create_user(username=username, password='temp001')
			interface.alsoProvides( user, IRecreatableUser )

	@classmethod
	def setUp(cls):
		# Must implement!
		cls.__old_library = component.getUtility(IContentPackageLibrary)
		component.provideUtility(LegacyInstructedCourseApplicationTestLayer._setup_library(cls),
								 IContentPackageLibrary)
		_do_then_enumerate_library(cls._user_creation, sync_libs=True)

	@classmethod
	def tearDown(cls):
		# Must implement!
		# Clean up any side effects of these content packages being
		# registered

		def cleanup():
			_reset_site_libs()
			cls.__old_library.resetContentPackages()
			component.provideUtility(cls.__old_library, IContentPackageLibrary)
			_delete_users(cls._instructors)
			_clear_catalogs(cls._sites_names)
			_delete_catalogs(cls._sites_names)

		_do_then_enumerate_library(cleanup)
		del cls.__old_library

# Export the new-style stuff as default
InstructedCourseApplicationTestLayer = PersistentInstructedCourseApplicationTestLayer
