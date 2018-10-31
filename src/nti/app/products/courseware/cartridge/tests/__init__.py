#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.intid.interfaces import IIntIds

import zope.testing.cleanup

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.outlines import CourseOutline
from nti.contenttypes.courses.outlines import CourseOutlineContentNode
from nti.contenttypes.courses.outlines import CourseOutlineNode

from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.contenttypes.presentation.media import NTIMediaRef


class SharedConfiguringTestLayer(ZopeComponentLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin):

    set_up_packages = ('nti.dataserver',
                       'nti.contenttypes.courses',
                       'nti.contentlibrary',
                       'nti.app.contenttypes.presentation',
                       'nti.app.products.courseware',)

    @classmethod
    def setUp(cls):
        cls.setUpPackages()

    @classmethod
    def tearDown(cls):
        cls.tearDownPackages()
        zope.testing.cleanup.cleanUp()

    @classmethod
    def testSetUp(cls, test=None):
        pass

    @classmethod
    def testTearDown(cls):
        pass

import unittest


class CommonCartridgeLayerTest(unittest.TestCase):
    layer = SharedConfiguringTestLayer

    @Lazy
    def test_course(self):
        intids = component.getUtility(IIntIds)

        course = ContentCourseInstance()
        intids.register(course)

        # Adapting will create a catalog entry
        entry = ICourseCatalogEntry(course)
        entry.title = u'Test Course'
        entry.ntiid = 'test_entry'
        intids.register(entry)

        outline = CourseOutline()
        course.Outline = outline  # Don't use the Outline property to create because it requires a Connection
        outline.title = u'Course Outline'
        intids.register(outline)

        unit = CourseOutlineNode()
        unit.title = u'Unit 1'
        outline.append(unit)
        intids.register(unit)

        content_node = CourseOutlineContentNode()
        content_node.title = u'Lesson 1'
        content_node.LessonOverviewNTIID = 'abc'
        unit.append(content_node)
        intids.register(content_node)

        lesson_obj = NTILessonOverView()
        lesson_obj.ntiid = 'abc'
        lesson_obj.title = u'Lesson 1'
        intids.register(lesson_obj)
        gsm = component.getGlobalSiteManager()
        gsm.registerUtility(lesson_obj, INTILessonOverview, name='abc')
        lesson = INTILessonOverview(content_node)

        overview_group1 = NTICourseOverViewGroup()
        overview_group1.title = u'OverView Group 1'
        lesson.append(overview_group1)
        intids.register(overview_group1)

        overview_group2 = NTICourseOverViewGroup()
        overview_group2.title = u'OverView Group 2'
        lesson.append(overview_group2)
        intids.register(overview_group2)

        media_ref1 = NTIMediaRef()
        media_ref1.title = u'Media 1.1'
        overview_group1.append(media_ref1)
        intids.register(media_ref1)

        media_ref2 = NTIMediaRef()
        media_ref2.title = u'Media 1.2'
        overview_group1.append(media_ref2)
        intids.register(media_ref2)

        media_ref3 = NTIMediaRef()
        media_ref3.title = u'Media 2.1'
        overview_group2.append(media_ref3)
        intids.register(media_ref3)

        return course
