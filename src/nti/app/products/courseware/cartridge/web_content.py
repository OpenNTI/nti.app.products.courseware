#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import shutil
from collections import defaultdict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds
from zope.schema.fieldproperty import createFieldProperties

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IIMSWebContentUnit)
class AbstractIMSWebContent(object):

    createFieldProperties(IIMSWebContentUnit)

    def __init__(self, context):
        self.context = context
        self.dependencies = defaultdict(list)

    def create_dirname(self, path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    def copy_file_resource(self, src_object, target_path):
        self.create_dirname(target_path)
        with open(target_path, 'w') as dest:
            shutil.copyfileobj(src_object, dest)
            return True

    def copy_resource(self, source_path, target_path):
        if os.path.exists(source_path):
            self.create_dirname(target_path)
            shutil.copy(source_path, target_path)
            return True

    def write_resource(self, path, resource):
        self.create_dirname(path)
        with open(path, 'w') as fd:
            fd.write(resource.encode('utf-8'))
        return True

    @Lazy
    def intids(self):
        intids = component.getUtility(IIntIds)
        return intids

    @Lazy
    def identifier(self):
        # Use register here as some of these aren't already intid'd
        # The usage of this should not persist so the intid will disappear after the export ends
        return self.intids.register(self)
    __name__ = identifier

    def export(self, dirname):
        raise NotImplementedError
