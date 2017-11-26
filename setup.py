import sys

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

from pathlib import Path


def read_version(package):
    with (Path(package) / '__init__.py').open() as fd:
        for line in fd:
            if line.startswith('__version__ = '):
                return line.split()[-1].strip().strip("'")


version = read_version('kube_downscaler')


class PyTest(TestCommand):

    user_options = [('cov-html=', None, 'Generate junit html report')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.cov = None
        self.pytest_args = ['--cov', 'kube_downscaler', '--cov-report', 'term-missing', '-v']
        self.cov_html = False

    def finalize_options(self):
        TestCommand.finalize_options(self)
        if self.cov_html:
            self.pytest_args.extend(['--cov-report', 'html'])
        self.pytest_args.extend(['tests'])

    def run_tests(self):
        import pytest

        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


def readme():
    return open('README.rst', encoding='utf-8').read()


tests_require = [
    'pytest',
    'pytest-cov'
]

setup(
    name='kube-downscaler',
    packages=find_packages(),
    version=version,
    description='Kubernetes Down Scaler',
    long_description=readme(),
    author='Henning Jacobs',
    url='https://github.com/hjacobs/kube-downscaler',
    keywords='kubernetes operations autoscaler',
    license='GNU General Public License v3 (GPLv3)',
    tests_require=tests_require,
    extras_require={'tests': tests_require},
    cmdclass={'test': PyTest},
    test_suite='tests',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Topic :: System :: Clustering',
        'Topic :: System :: Monitoring',
    ],
    entry_points={'console_scripts': ['kube-downscaler = kube_downscaler.main:main']}
)
