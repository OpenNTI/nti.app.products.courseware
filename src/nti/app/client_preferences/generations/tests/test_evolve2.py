#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import json
import fudge

from zope.preference import interfaces as pref_interfaces

from zope.security.interfaces import IPrincipal
from zope.security.management import newInteraction, endInteraction

import nti.appserver
import nti.dataserver

from nti.dataserver.users.preferences import EntityPreferences
from nti.dataserver.users import interfaces as user_interfaces

from ..evolve2 import evolve, _Participation

from nti.dataserver.utils.example_database_initializer import ExampleDatabaseInitializer

from nti.dataserver.tests.mock_dataserver import ConfiguringTestBase
from nti.dataserver.tests.mock_dataserver import mock_db_trans, WithMockDS

from nti.deprecated import hides_warnings

from hamcrest import (assert_that, none, is_)

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

class TestEvolve2(ConfiguringTestBase):
	set_up_packages = (nti.dataserver, 'nti.app.client_preferences')

	@hides_warnings
	@WithMockDS
	def test_evolve2(self):
		with mock_db_trans( ) as conn:
			context = fudge.Fake().has_attr( connection=conn )
			ExampleDatabaseInitializer(max_test_users=5,skip_passwords=True).install( context )

			ds_folder = context.connection.root()['nti.dataserver']
			user = ds_folder['users']['jason.madden@nextthought.com']
			prefs = user_interfaces.IEntityPreferences(user)
			prefs.update(json.loads(_user_preferences))

		with mock_db_trans(  ) as conn:
			context = fudge.Fake().has_attr( connection=conn )
			evolve(context)

		with mock_db_trans( ) as conn:
			ds_folder = context.connection.root()['nti.dataserver']
			user = ds_folder['users']['jason.madden@nextthought.com']

			key = EntityPreferences.__module__ + '.' + EntityPreferences.__name__
			ep = getattr(json, '__annotations__', {}).get(key, None)
			assert_that(ep, is_(none()))

			principal = IPrincipal(user)
			newInteraction(_Participation(principal))

			root_prefs = pref_interfaces.IUserPreferences(user)
			assert_that(root_prefs.WebApp.preferFlashVideo, is_(True))

			assert_that(root_prefs.ChatPresence.Active.status, is_('Back from lunch'))
			assert_that(root_prefs.ChatPresence.Available.status, is_('Back from lunch'))
			assert_that(root_prefs.ChatPresence.Away.status, is_('Back from breakfast'))
			assert_that(root_prefs.ChatPresence.DND.status, is_('Back from dinner'))

			endInteraction()
