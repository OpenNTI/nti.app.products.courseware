import codecs
from setuptools import setup
from setuptools import find_packages

entry_points = {
    'console_scripts': [
        "nti_acl_forum_creator = nti.app.products.courseware.scripts.nti_acl_forum_creator:main",
        "nti_unregister_invalid_nodes = nti.app.products.courseware.scripts.nti_unregister_invalid_nodes:main",
        "nti_course_enrollment_migrator = nti.app.products.courseware.scripts.nti_course_enrollment_migrator:main",
    ],
    "z3c.autoinclude.plugin": [
        'target = nti.app.products',
    ],
}


TESTS_REQUIRE = [
    'nti.app.testing',
    'nti.testing',
    'zope.testrunner',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.products.courseware',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Umbrella product to support integrated courseware",
    long_description=(
        _read('README.rst')
        + '\n\n'
        + _read("CHANGES.rst")
    ),
    license='Apache',
    keywords='pyramid products courses integration',
    classifiers=[
        'Framework :: Zope',
        'Framework :: Pyramid',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.app.products.courseware",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app', 'nti.app.products'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'BTrees',
        'beautifulsoup4',
        'isodate',
        'nti.app.assessment',
        'nti.app.contenttypes.presentation',
        'nti.app.products.acclaim',
        'nti.app.products.webinar',
        'nti.app.invitations',
        'nti.app.site',
        'nti.base',
        'nti.contentlibrary',
        'nti.contenttypes.completion',
        'nti.contenttypes.courses',
        'nti.contenttypes.presentation',
        'nti.coremetadata',
        'nti.externalization',
        'nti.links',
        'nti.namedfile',
        'nti.ntiids',
        'nti.property',
        'nti.publishing',
        'nti.recorder',
        'nti.schema',
        'nti.traversal',
        'nti.wref',
        'nti.zodb',
        'persistent',
        'pyramid',
        'repoze.lru',
        'requests',
        'zc.intid',
        'ZODB',
        'zope.annotation',
        'zope.cachedescriptors',
        'zope.component',
        'zope.container',
        'zope.deferredimport',
        'zope.dottedname',
        'zope.event',
        'zope.i18n',
        'zope.i18nmessageid',
        'zope.interface',
        'zope.intid',
        'zope.lifecycleevent',
        'zope.location',
        'zope.pluggableauth',
        'zope.publisher',
        'zope.security',
        'zope.securitypolicy',
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
    },
    entry_points=entry_points
)
