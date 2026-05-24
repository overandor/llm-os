"""
Setup configuration for Enterprise LLM Suite macOS app bundling.
"""
from setuptools import setup

APP = ['enterprise_gui.py']
DATA_FILES = [
    ('enterprise_data', ['enterprise_suite.py', 'enterprise_server.py']),
]
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,
    'plist': {
        'CFBundleName': 'Enterprise LLM Suite',
        'CFBundleDisplayName': 'Enterprise LLM Suite',
        'CFBundleIdentifier': 'com.membra.enterprise-llm-suite',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        'NSRequiresAquaSystemAppearance': False,
    },
    'packages': [
        'llm_os',
    ],
    'includes': [
        'enterprise_suite',
        'enterprise_server',
        'Cocoa',
        'AppKit',
        'Foundation',
        'PyObjCTools',
        'sqlite3',
        'json',
        'hashlib',
        'pathlib',
        'dataclasses',
        'enum',
        'datetime',
        'fastapi',
        'uvicorn',
        'pydantic',
        'starlette',
        'secrets',
    ],
    'excludes': [
        'tkinter',
        'matplotlib',
        'pytest',
        'torch',
        'numpy',
    ],
    'optimize': 2,
    'site_packages': True,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    name='Enterprise LLM Suite',
    version='1.0.0',
)
