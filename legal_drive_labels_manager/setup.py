#!/usr/bin/env python
"""
Setup script for Legal Drive Labels Manager.
"""

import os
import sys
from setuptools import setup, find_packages

# Read version from __init__.py
with open(os.path.join('legal_drive_labels_manager', '__init__.py'), 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"\'')
            break
    else:
        version = '0.1.0'

# Read long description from README.md
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Core requirements
requirements = [
    'google-api-python-client>=2.0.0',
    'google-auth-httplib2>=0.1.0',
    'google-auth-oauthlib>=0.4.0',
]

setup(
    name='legal-drive-labels-manager',
    version=version,
    description='A tool for legal teams to manage Google Drive Labels without direct API access',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Organization',
    author_email='legal@yourdomain.com',
    url='https://github.com/yourdomain/legal-drive-labels-manager',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        'visualization': [
            'pandas>=1.0.0',
            'matplotlib>=3.0.0',
            'seaborn>=0.11.0',
        ],
        'dev': [
            'pytest>=6.0.0',
            'black>=22.0.0',
            'isort>=5.0.0',
            'mypy>=0.9.0',
            'flake8>=4.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'drive-labels=legal_drive_labels_manager.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Legal Industry',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    python_requires='>=3.7',
)