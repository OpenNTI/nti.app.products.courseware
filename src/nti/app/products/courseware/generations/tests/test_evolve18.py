#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_key
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

from nti.app.products.courseware.generations import evolve18

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestEvolve18(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_evolve(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.entry_ntiid)
            course = ICourseInstance(entry)
            resources = course_resources(course, create=True)

            bleach = CourseContentFolder()
            resources[u'bleach'] = bleach
            bleach.__dict__['filename'] = u'bleach'
            bleach.__dict__['use_blobs'] = True

            ichigo = CourseContentFile()
            bleach[u'ichigo.txt'] = ichigo
            ichigo.name = u'ichigo.txt'
            ichigo.filename = u'ichigo'

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            resources = course_resources(course, create=False)
            evolve18.process_course_resources(resources)
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            resources = course_resources(course, create=False)
            bleach = resources['bleach']
            assert_that(bleach, has_property('name', 'bleach'))
            assert_that(bleach, has_property('filename', 'bleach'))
            assert_that(bleach, has_property('__name__', 'bleach'))
            assert_that(bleach.__dict__, does_not(has_key('filename')))
            assert_that(bleach.__dict__, does_not(has_key('use_blobs')))
        
            ichigo = bleach['ichigo.txt']
            assert_that(ichigo, has_property('filename', 'ichigo.txt'))
            assert_that(ichigo, has_property('__name__', 'ichigo.txt'))
            assert_that(ichigo.__dict__, does_not(has_key('name')))
