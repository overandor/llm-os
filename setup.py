"""
Setup configuration for py2app macOS app bundling.
"""
from setuptools import setup

APP = ['llm_os/__main__.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,
    'plist': {
        'CFBundleName': 'LLM OS',
        'CFBundleDisplayName': 'LLM OS',
        'CFBundleIdentifier': 'com.membra.llm-os',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
    },
    'packages': [
        'llm_os',
        'llm_os.subsystems',
        'llm_os.memory',
    ],
    'includes': [
        'typer',
        'rich',
        'pydantic',
        'psutil',
        'fastapi',
        'uvicorn',
    ],
    'excludes': [
        'tkinter',
        'matplotlib',
        'pytest',
        'numpy',
    ],
    'optimize': 2,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    name='LLM OS',
    version='0.1.0',
)
