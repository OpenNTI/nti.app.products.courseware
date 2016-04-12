#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 4

from zope import interface

from zope.generations.generations import SchemaManager as BaseSchemaManager

from zope.generations.interfaces import IInstallableSchemaManager

from nti.app.products.courseware.generations import evolve2

@interface.implementer(IInstallableSchemaManager)
class _SchemaManager(BaseSchemaManager):
	"""
	A schema manager that we can register as a utility in ZCML.
	"""

	def __init__(self):
		super(_SchemaManager, self).__init__(
						generation=generation,
						minimum_generation=generation,
						package_name='nti.app.products.courseware.generations')

	def install(self, context):
		evolve(context)

def evolve(context):
	evolve2.evolve(context)
