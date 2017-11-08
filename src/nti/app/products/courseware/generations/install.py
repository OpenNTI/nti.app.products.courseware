#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.generations.generations import SchemaManager as BaseSchemaManager

from zope.generations.interfaces import IInstallableSchemaManager

generation = 18

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IInstallableSchemaManager)
class _SchemaManager(BaseSchemaManager):

    def __init__(self):
        super(_SchemaManager, self).__init__(
            generation=generation,
            minimum_generation=generation,
            package_name='nti.app.products.courseware.generations')

    def install(self, context):
        evolve(context)


def evolve(context):
    pass
