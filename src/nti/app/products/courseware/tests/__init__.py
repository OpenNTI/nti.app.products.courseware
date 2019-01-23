#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import gc

import os
import shutil
import tempfile

from zope import component
from zope import interface

from zope.component.interfaces import IComponents

import ZODB

import zope.testing.cleanup

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.users.interfaces import IRecreatableUser

from nti.dataserver.users.users import User

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.app.testing.application_webtest import ApplicationTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import mock_db_trans

from nti.dataserver.tests.mock_dataserver import DSInjectorMixin
from nti.dataserver.tests.mock_dataserver import DataserverLayerTest

from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin


def setChameleonCache(cls):
    cls.old_cache_dir = os.getenv('CHAMELEON_CACHE')
    cls.new_cache_dir = tempfile.mkdtemp(prefix="cham_")
    os.environ['CHAMELEON_CACHE'] = cls.new_cache_dir


def restoreChameleonCache(cls):
    shutil.rmtree(cls.new_cache_dir, True)
    os.environ['CHAMELEON_CACHE'] = cls.old_cache_dir


class SharedConfiguringTestLayer(ZopeComponentLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin,
                                 DSInjectorMixin):

    set_up_packages = ('nti.dataserver',
                       'nti.invitations',
                       'nti.contenttypes.completion',
                       'nti.app.invitations',
                       'nti.app.products.webinar',
                       'nti.app.products.courseware')

    @classmethod
    def setUp(cls):
        setChameleonCache(cls)
        cls.setUpPackages()

    @classmethod
    def tearDown(cls):
        cls.tearDownPackages()
        zope.testing.cleanup.cleanUp()

    @classmethod
    def testSetUp(cls, test=None):
        cls.setUpTestDS(test)

    @classmethod
    def testTearDown(cls):
        restoreChameleonCache(cls)


class CourseLayerTest(DataserverLayerTest):
    layer = SharedConfiguringTestLayer


def publish_ou_course_entries():
    lib = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
    if lib is None:
        return
    try:
        del lib.contentPackages
    except AttributeError:
        pass
    lib.syncContentPackages()


def _do_then_enumerate_library(do, sync_libs=False):

    database = ZODB.DB(ApplicationTestLayer._storage_base,
                       database_name='Users')

    @WithMockDS(database=database)
    def _create():
        with mock_db_trans():
            do()
            publish_ou_course_entries()
            if sync_libs:
                from nti.app.contentlibrary.views.sync_views import _SyncAllLibrariesView
                view = _SyncAllLibrariesView(None)
                view._SLEEP = False  # see comments in the view class
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
        User.delete_user(username)


def _clear_catalogs(site_names=()):
    component.getGlobalSiteManager().getUtility(ICourseCatalog).clear()
    for name in site_names or ():
        component.getUtility(IComponents, name=name).getUtility(
            ICourseCatalog).clear()


def _delete_catalogs(site_names=()):
    from nti.site.site import get_site_for_site_names
    for name in site_names or ():
        site = get_site_for_site_names((name,))
        cc = site.getSiteManager().getUtility(ICourseCatalog)
        for x in list(cc):
            del cc[x]


class LegacyInstructedCourseApplicationTestLayer(ApplicationTestLayer):

    _library_path = 'Library'
    _instructors = (u'harp4162',)
    _sites_names = ('platform.ou.edu',)

    @classmethod
    def _user_creation(cls):
        for username in cls._instructors:
            if User.get_user(username) is None:
                user = User.create_user(username=username,
                                        password=u'temp001')
                interface.alsoProvides(user, IRecreatableUser)

    @staticmethod
    def _setup_library(layer, *unused_args, **unused_kwargs):
        from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library
        # FIXME: We load CLC in both global and site level libraries.
        # This caused some weird ConnectionStateErrors in contentlibrary.subscribers when
        # tearing down the library (now worked around). The registered items were ghosted
        # by the time we query for them in the site level tear down.
        lib = Library(
	            paths=(
	                os.path.join(
	                    os.path.dirname(__file__),
	                    layer._library_path,
	                    'IntroWater'),
	                os.path.join(
	                    os.path.dirname(__file__),
	                    layer._library_path,
	                    'CLC3403_LawAndJustice')))
        return lib

    @staticmethod
    def _install_library(layer, *enum_args, **enum_kwargs):
        gsm = component.getGlobalSiteManager()
        layer._old_library = gsm.queryUtility(IContentPackageLibrary)
        if layer._old_library is None:
            print("WARNING: A previous layer removed the global IContentPackageLibrary",
                  layer)
        layer._new_library = LegacyInstructedCourseApplicationTestLayer._setup_library(
            layer)
        gsm.registerUtility(layer._new_library, IContentPackageLibrary)
        _do_then_enumerate_library(*enum_args, **enum_kwargs)

    @staticmethod
    def _uninstall_library(layer):
        _reset_site_libs()
        # Bypass inheritance for these, make sure we're only getting from this
        # class.
        new_lib = layer.__dict__['_new_library']
        old_lib = layer.__dict__['_old_library']
        gsm = component.getGlobalSiteManager()
        gsm.unregisterUtility(new_lib, IContentPackageLibrary)
        if old_lib is not None:
            old_lib.resetContentPackages()
            gsm.registerUtility(old_lib, IContentPackageLibrary)
        else:
            print("WARNING: When tearing layer", layer,
                  "no IContentPackageLibrary to restore")
        del layer._old_library
        del layer._new_library
        gc.collect()

    @classmethod
    def setUp(cls):
        setChameleonCache(cls)

        # Must implement!
        cls._install_library(cls, cls._user_creation)

        database = ZODB.DB(ApplicationTestLayer._storage_base,
                           database_name='Users')

        @WithMockDS(database=database)
        def _drop_any_direct_catalog_references():
            for name in cls._sites_names:
                with mock_db_trans(site_name=name):
                    # # make sure they get looked up through the catalog
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
            cls._uninstall_library(cls)
            _delete_users(cls._instructors)
            _clear_catalogs(cls._sites_names)

        _do_then_enumerate_library(cleanup)

    testSetUp = classmethod(lambda cls: None)

    @classmethod
    def testTearDown(cls):
        restoreChameleonCache(cls)


class RestrictedInstructedCourseApplicationTestLayer(ApplicationTestLayer):

    _library_path = 'RestrictedLibrary'
    _instructors = (u'harp4162',)
    _sites_names = ('platform.ou.edu',)

    @classmethod
    def _user_creation(cls):
        for username in cls._instructors:
            if User.get_user(username) is None:
                user = User.create_user(username=username,
                                        password=u'temp001')
                interface.alsoProvides(user, IRecreatableUser)

    @classmethod
    def setUp(cls):
        # Must implement!
        setChameleonCache(cls)
        LegacyInstructedCourseApplicationTestLayer._install_library(
            cls, cls._user_creation)

    @classmethod
    def tearDown(cls):
        # Must implement!
        # Clean up any side effects of these content packages being
        # registered
        def cleanup():
            LegacyInstructedCourseApplicationTestLayer._uninstall_library(cls)
            _delete_users(cls._instructors)
            _clear_catalogs(cls._sites_names)

        _do_then_enumerate_library(cleanup)

    testSetUp = classmethod(lambda cls: None)

    @classmethod
    def testTearDown(cls):
        restoreChameleonCache(cls)


class NotInstructedCourseApplicationTestLayer(ApplicationTestLayer):

    _library_path = 'PersistentLibrary'
    _sites_names = ('platform.ou.edu',)

    @classmethod
    def setUp(cls):
        # Must implement!
        setChameleonCache(cls)
        LegacyInstructedCourseApplicationTestLayer._install_library(
            cls,
            lambda: lambda: True, sync_libs=True)

    @classmethod
    def tearDown(cls):
        # Must implement!
        # Clean up any side effects of these content packages being
        # registered

        def cleanup():
            LegacyInstructedCourseApplicationTestLayer._uninstall_library(cls)
            _clear_catalogs(cls._sites_names)
            _delete_catalogs(cls._sites_names)

        _do_then_enumerate_library(cleanup)

    testSetUp = classmethod(lambda cls: None)

    @classmethod
    def testTearDown(cls):
        restoreChameleonCache(cls)


class PersistentInstructedCourseApplicationTestLayer(ApplicationTestLayer):
    # A mix of new and old-style courses

    _library_path = 'PersistentLibrary'
    _instructors = (u'harp4162', u'tryt3968', u'jmadden', u"cs1323_instructor")
    _sites_names = ('platform.ou.edu',)

    @classmethod
    def _user_creation(cls):
        for username in cls._instructors:
            if User.get_user(username) is None:
                user = User.create_user(username=username,
                                        password=u'temp001')
                interface.alsoProvides(user, IRecreatableUser)

    @classmethod
    def setUp(cls):
        # Must implement!
        setChameleonCache(cls)
        LegacyInstructedCourseApplicationTestLayer._install_library(
            cls, cls._user_creation, sync_libs=True)

    @classmethod
    def tearDown(cls):
        # Must implement!
        # Clean up any side effects of these content packages being
        # registered

        def cleanup():
            LegacyInstructedCourseApplicationTestLayer._uninstall_library(cls)
            _delete_users(cls._instructors)
            _clear_catalogs(cls._sites_names)
            _delete_catalogs(cls._sites_names)

        _do_then_enumerate_library(cleanup)

    testSetUp = classmethod(lambda cls: None)

    @classmethod
    def testTearDown(cls):
        restoreChameleonCache(cls)


# Export the new-style stuff as default
InstructedCourseApplicationTestLayer = PersistentInstructedCourseApplicationTestLayer
