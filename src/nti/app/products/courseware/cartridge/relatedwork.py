#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import shutil

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(INTIRelatedWorkRef)
class RelatedWorkHandler(AbstractElementHandler):

    @Lazy
    def href(self):
        return self.context.href or ''
    
    @Lazy
    def is_content(self):
        return "application/vnd.nextthought.content" == self.context.type

    @Lazy
    def is_external_link(self):
        return "application/vnd.nextthought.externallink" == self.context.type

    @Lazy
    def is_local_resource(self):
        # pylint: disable=no-member
        return self.is_external_link and self.href.startswith('resources/')

    @Lazy
    def target(self):
        return find_object_with_ntiid(self.context.target)

    def iter_items(self):
        return ()

    def iter_resources(self):
        return ()

    # cartridge

    def create_dirname(self, path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    def copy_resource(self, source_path, target_path):
        if os.path.exists(source_path):
            self.create_dirname(target_path)
            shutil.copy(source_path, target_path)
            return True

    def write_local(self, archive):
        package = find_interface(self.context, IContentPackage, strict=False)
        root = getattr(package, 'root', None)
        if not IFilesystemBucket.providedBy(root):
            logger.warning("Unsupported bucket Boto?")
        elif self.href:
            source_path = os.path.join(root.absolute_path, self.href)
            target_path = os.path.join(archive, self.href)
            self.copy_resource(source_path, target_path)

    def write_content(self, archive):
        unit = self.target
        package = find_interface(unit, IContentPackage, strict=False)
        root = getattr(package, 'root', None)
        if not IFilesystemBucket.providedBy(root):
            logger.warning("Unsupported bucket Boto?")
        else:
            rel_path = unit.href  # pylint: disable=no-member
            source_path = os.path.join(root.absolute_path, rel_path)
            target_path = os.path.join(archive, rel_path)
            self.copy_resource(source_path, target_path)

    def write_to(self, archive):
        if self.is_content and self.target is not None:
            self.write_content(archive)
        elif self.is_local_resource:
            self.write_local(archive)
