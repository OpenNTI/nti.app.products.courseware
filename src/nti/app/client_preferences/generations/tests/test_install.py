#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import nti.appserver
import nti.dataserver

from nti.dataserver.users import interfaces as user_interfaces

from nti.dataserver.tests.mock_dataserver import ConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import mock_db_trans, WithMockDS

from hamcrest import assert_that
from hamcrest import has_entry
from .. import install

_user_preferences = """
{
    "webapp_kalturaPreferFlash": true,
    "presence": {
        "active": "available",
        "available": {
            "show": "chat",
            "status": "Back from lunch",
            "type": "available"
        },
        "away": {
            "show": "away",
            "status": "Back from breakfast",
            "type": "available"
        },
        "dnd": {
            "show": "dnd",
            "status": "Back from dinner",
            "type":"available"
        },
        "unavailable": {
            "show": "chat",
            "type": "unavailable"
        }
     }
}"""

class TestInstall(ConfiguringTestBase):
	set_up_packages = (nti.dataserver, 'nti.app.client_preferences')

	@WithMockDS
	def test_install(self):
		with mock_db_trans( ) as conn:
			assert_that( conn.root(),
						 has_entry( 'zope.generations',
									has_entry( 'nti.dataserver:nti.app.client_preferences',
											   install.generation ) ) )
