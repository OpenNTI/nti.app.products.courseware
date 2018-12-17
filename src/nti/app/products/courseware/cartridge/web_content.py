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

from nti.app.contenttypes.presentation.decorators.assets import _get_item_content_package
from nti.app.contenttypes.presentation.decorators.assets import _path_exists_in_package

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

from nti.contentlibrary.interfaces import IContentPackage

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class WebContentMixin(object):

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
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier


@interface.implementer(IIMSWebContentUnit)
class AbstractIMSWebContent(WebContentMixin):

    createFieldProperties(IIMSWebContentUnit)

    def __init__(self, context):
        self.context = context
        self.dependencies = defaultdict(list)

    def export(self, dirname):
        raise NotImplementedError


@interface.implementer(IIMSWebContentUnit)
class IMSWebContent(AbstractIMSWebContent):
    """
    Wrapper class for rendered content files that are not associated with an object
    """

    def __init__(self, context, path_to):
        super(IMSWebContent, self).__init__(context)
        self.path_to = path_to

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def content_package(self):
        package = find_interface(self.context, IContentPackage, strict=False)
        if package is None and getattr(self.context, 'target', False):
            target = find_object_with_ntiid(self.context.target)
            package = find_interface(target, IContentPackage, strict=False)
        if package is None:
            # ok lets try the hammer...
            for name in ('href', 'icon'):
                value = getattr(self.context, name, None)
                if value and not value.startswith('/') and '://' not in value:
                    if     package is None \
                        or not _path_exists_in_package(value, package):
                        # We make sure each url is in the correct package.
                        package = _get_item_content_package(self.context, value)
        if not package:
            raise CommonCartridgeExportException(u'Unable to locate a content package for %s' % self.context)
        return package

    @Lazy
    def filename(self):
        return self.path_to

    @Lazy
    def content_directory(self):
        dirname = getattr(self.content_package, 'dirname', None)
        if dirname is None:
            raise CommonCartridgeExportException(u'Corrupt content package %s' % self.content_package)
        return self.content_package.dirname

    def export(self, dirname):
        source_path = os.path.join(self.content_directory, self.path_to)
        target_path = os.path.join(dirname, self.path_to)
        self.copy_resource(source_path, target_path)


@interface.implementer(IIMSWebContentUnit)
class MathJAXWebContent(WebContentMixin):

    createFieldProperties(IIMSWebContentUnit)

    def __init__(self, content):
        self.content = content

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def filename(self):
        return self.identifier + '.html'

    def export(self, dirname):
        target_path = os.path.join(dirname, self.filename)
        self.write_resource(target_path, self.content)
        return True
