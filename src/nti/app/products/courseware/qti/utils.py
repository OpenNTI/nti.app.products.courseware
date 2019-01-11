#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from bs4 import BeautifulSoup

from six.moves import urllib_parse

from nti.app.products.courseware.cartridge.web_content import IMSWebContent
from nti.app.products.courseware.cartridge.web_content import S3WebContent

from nti.common import random

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def is_internal_resource(href):
    return not bool(urllib_parse.urlparse(href).scheme) and not href.startswith('#')


def is_s3(href):
    return bool(urllib_parse.urlparse(href).scheme) and 'content.nextthought.com' in href


def update_external_resources(context, html, path_prefix='dependencies'):
    soup = BeautifulSoup(html, features='html.parser')
    deps = []
    to_be_replaced = []
    for tag in soup.recursiveChildGenerator():
        if hasattr(tag, 'name') and tag.name == 'a' and \
                hasattr(tag, 'attrs') and 'href' in tag.attrs:
            href = tag.attrs['href']
            if is_internal_resource(href):
                deps.append(IMSWebContent(context, href))
                if href.startswith('/'):
                    href = href[1:]
                href = os.path.join(path_prefix, href)
                tag.attrs['href'] = os.path.join('$IMS-CC-FILEBASE$', href)
            elif href.startswith('#'):
                span = soup.new_tag('span')
                span.string = tag.text
                to_be_replaced.append((span, tag))
            elif is_s3(href):
                file_hash = random.generate_random_string(4)
                deps.append(S3WebContent(href, file_hash))
                path = urllib_parse.urlparse(href).path[1:]
                filename = os.path.basename(path)
                filename = '%s_%s' % (file_hash, filename)
                path = os.path.join(path_prefix, filename)
                tag.attrs['href'] = os.path.join('$IMS-CC-FILEBASE$', path)
        if hasattr(tag, 'name') and tag.name == 'img' and \
                hasattr(tag, 'attrs') and 'src' in tag.attrs:
            src = tag.attrs['src']
            if is_internal_resource(src):
                deps.append(IMSWebContent(context, src))
                if src.startswith('/'):
                    src = src[1:]
                src = os.path.join(path_prefix, src)
                tag.attrs['src'] = os.path.join('$IMS-CC-FILEBASE$', src)
            elif is_s3(src):
                file_hash = random.generate_random_string(4)
                deps.append(S3WebContent(src, file_hash))
                path = urllib_parse.urlparse(src).path[1:]
                filename = os.path.basename(path)
                filename = '%s_%s' % (file_hash, filename)
                path = os.path.join(path_prefix, filename)
                tag.attrs['src'] = os.path.join('$IMS-CC-FILEBASE$', path)
    for new, old in to_be_replaced:
        old.replace_with(new)

    return soup.decode(), deps


def mathjax_parser(html):
    soup = BeautifulSoup(html, features='html.parser')
    mathjax = soup.find_all('span', class_='mathjax math tex2jax_process')
    for mj in mathjax:
        nobr = mj.find_all('nobr')
        for tag in nobr:
            # nobr isn't supported in canvas. We replace it with a valid css property
            tag.name = 'span'
            tag.attrs = {'style': 'white-space: nowrap; font-size: 14px;'}
    return soup.decode()
