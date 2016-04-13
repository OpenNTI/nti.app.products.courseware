import codecs
from setuptools import setup, find_packages

VERSION = '0.0.0'

entry_points = {
	'console_scripts': [
		"nti_course_exporter = nti.app.products.courseware.scripts.nti_course_exporter:main",
		"nti_course_importer = nti.app.products.courseware.scripts.nti_course_importer:main",
		"nti_acl_forum_creator = nti.app.products.courseware.scripts.nti_acl_forum_creator:main",
		"nti_unregister_invalid_nodes = nti.app.products.courseware.scripts.nti_unregister_invalid_nodes:main",
		"nti_course_enrollment_migrator = nti.app.products.courseware.scripts.nti_course_enrollment_migrator:main",
	],
	"z3c.autoinclude.plugin": [
		'target = nti.app.products',
	],
}

setup(
	name='nti.app.products.courseware',
	version=VERSION,
	author='Jason Madden',
	author_email='jason@nextthought.com',
	description="Umbrella product to support integrated courseware",
	long_description=codecs.open('README.rst', encoding='utf-8').read(),
	license='Proprietary',
	keywords='pyramid course',
	classifiers=[
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Framework :: Pyramid',
	],
	packages=find_packages('src'),
	package_dir={'': 'src'},
	namespace_packages=['nti', 'nti.app', 'nti.app.products'],
	install_requires=[
		'setuptools'
	],
	entry_points=entry_points
)
