#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Application (request) specific traversal for course instances and enrollments, etc.
Primarily, we want to bring the usual automatic-conversion to path adapters into
play for ease of extension by other packages. (Hmm, perhaps we ought to make that
part of the default traversal).


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

import pyramid.interfaces
from zope.traversing.interfaces import ITraversable

from zope.traversing.adapters import DefaultTraversable
from zope.container.traversal import ContainerTraversable

from nti.appserver._dataserver_pyramid_traversal import adapter_request

from .interfaces import ICourseInstanceEnrollment
from nti.contenttypes.courses.interfaces import ICourseInstance

@interface.implementer(ITraversable)
@component.adapter(ICourseInstance, pyramid.interfaces.IRequest)
class CourseTraversable(ContainerTraversable):

	def __init__( self, context, request=None ):
		super(CourseTraversable,self).__init__(context)
		self.context = context
		self.request = request

	def traverse( self, key, remaining_path ):
		try:
			return super(CourseTraversable,self).traverse(key, remaining_path)
		except KeyError:
			# Is there a named path adapter?
			return adapter_request( self.context, self.request ).traverse( key, remaining_path )


@interface.implementer(ITraversable)
@component.adapter(ICourseInstanceEnrollment, pyramid.interfaces.IRequest)
class CourseEnrollmentTraversable(DefaultTraversable):

	def __init__( self, context, request=None ):
		super(CourseEnrollmentTraversable,self).__init__(context)
		self.context = context
		self.request = request

	def traverse( self, key, remaining_path ):
		try:
			return super(CourseEnrollmentTraversable,self).traverse(key, remaining_path)
		except KeyError:
			# Is there a named path adapter?
			return adapter_request( self.context, self.request ).traverse( key, remaining_path )
