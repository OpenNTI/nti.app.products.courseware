#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.app.products.courseware.tests import LegacyInstructedCourseApplicationTestLayer

from nti.app.products.courseware.tests._workspaces import AbstractEnrollingBase

from nti.app.testing.application_webtest import ApplicationLayerTest

class TestLegacyWorkspace(AbstractEnrollingBase, ApplicationLayerTest):
	layer = LegacyInstructedCourseApplicationTestLayer
	individual_roster_accessible_to_instructor = False
