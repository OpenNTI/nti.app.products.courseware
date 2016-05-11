#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries

import fudge
import unittest

from nti.app.products.courseware.utils import get_course_invitations

class TestUtils(unittest.TestCase):

	@fudge.patch('nti.app.products.courseware.utils.traverse')
	@fudge.patch('nti.app.products.courseware.utils.get_course_and_parent')
	@fudge.patch('nti.app.products.courseware.utils.get_vendor_info')
	def test_get_course_invitations(self, mock_tr, mock_one, mock_vi):
		for data in ("One", ["One"]):
			mock_tr.is_callable().with_args().returns(data)
			mock_one.is_callable().with_args().returns([1])
			mock_vi.is_callable().with_args().returns(data)
			info = get_course_invitations(1)
			assert_that(info, has_length(1))
			assert_that(info[0], has_entries("Scope", "Public",
											 "Code","One",
											 "Description","Public"))
		
		data = [{"code":"Two", 'scope':'ForCredit',"description":"22"}]
		mock_tr.is_callable().with_args().returns(data)
		mock_one.is_callable().with_args().returns([1])
		mock_vi.is_callable().with_args().returns(data)
		info = get_course_invitations(1)
		assert_that(info, has_length(1))
		assert_that(info[0], has_entries("Scope", "ForCredit",
										 "Code","Two",
										 "Description","22"))
