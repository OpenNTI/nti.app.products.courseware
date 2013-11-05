#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to the course catalog and the courses workspace.

The initial strategy is to use a path adapter named Courses. It will
return something that isn't traversable (in this case, the Courses
workspace). Named views will be registered based on that to implement
the workspace collections.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.traversing.interfaces import IPathAdapter
from nti.dataserver.interfaces import IUser
from pyramid.interfaces import IRequest
from nti.appserver.interfaces import IUserService
from .interfaces import ICoursesWorkspace

from pyramid.view import view_defaults
from pyramid.view import view_config
from nti.dataserver import authorization as nauth
from nti.appserver.httpexceptions import HTTPNotFound

@interface.implementer(IPathAdapter)
@component.adapter(IUser, IRequest)
def CoursesPathAdapter(context, request):
	service = IUserService(context)
	workspace = ICoursesWorkspace(service)

	return workspace

@view_config(name='AllCourses')
@view_config(name='EnrolledCourses')
@view_defaults(route_name="objects.generic.traversal",
			   context=ICoursesWorkspace,
			   request_method='GET',
			   permission=nauth.ACT_READ,
			   renderer='rest')
class NamedCourseTypeView(object):

	def __init__(self, context, request):
		self.context = context
		self.request = request

	def __call__(self):
		for collection in self.context.collections:
			if collection.name == self.request.view_name:
				return collection
		raise HTTPNotFound()
