#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for viewing and updating preferences.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config

from nti.dataserver import authorization as nauth

from zope.preference.interfaces import IPreferenceGroup
# XXX: FIXME: Using private base views
from nti.appserver._view_utils import AbstractAuthenticatedView
from nti.appserver._view_utils import ModeledContentUploadRequestUtilsMixin

@view_config(route_name='objects.generic.traversal',
			 request_method='GET',
			 renderer='rest',
			 context=IPreferenceGroup,
			 permission=nauth.ACT_READ)
def PreferencesGetView(request):
	# This checks adaptation to annotations
	# and the security interaction all at the same time
	# Because we load the ++preference++ traversal namespace,
	# this is available at /path/to/principal/++preference++
	# (and sub-paths, nice! for automatic fetch-in-part)
	# TODO: We should supply etag and/or last modified for this
	# (does the default etag kick in?)
	return request.context


@view_config(route_name='objects.generic.traversal',
			 request_method='PUT',
			 renderer='rest',
			 context=IPreferenceGroup,
			 permission=nauth.ACT_UPDATE)
class PreferencesPutView(AbstractAuthenticatedView,ModeledContentUploadRequestUtilsMixin):
	# Although this is the UPDATE permission,
	# the prefs being updated are always those of the current user
	# implicitly, regardless of traversal path. We could add
	# an ACLProvider (and hook into the zope checker machinery?)
	# but that would be primarily for aesthetics
	def __call__(self):
		externalValue = self.readInput( )

		return self.updateContentObject( self.request.context, externalValue, notify=False )
