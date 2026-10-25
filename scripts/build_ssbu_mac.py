#!/usr/bin/env python3
"""Run the NSP pipeline with an optional separate SDK for Mac host packing.

DM_MAC_DEVELOPER_DIR selects a newer Command Line Tools SDK for the native
host and launcher while the existing Xcode supplies the Metal compiler.
"""
import functools
import importlib.util
import inspect
import os
from pathlib import Path
import sys

source = Path(__file__).with_name('build_ipa_from_nsp.py')
spec = importlib.util.spec_from_file_location('nsp_build', source)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def host_sdk(fn):
    @functools.wraps(fn)
    def run(*args, **kwargs):
        call = inspect.signature(fn).bind(*args, **kwargs)
        if developer_dir := os.environ.get('DM_MAC_DEVELOPER_DIR'):
            call.arguments['env'] = dict(call.arguments['env'], DEVELOPER_DIR=developer_dir)
        return fn(*call.args, **call.kwargs)
    return run


build.mac_host = host_sdk(build.mac_host)
build.mac_app = host_sdk(build.mac_app)

if __name__ == '__main__':
    sys.exit(build.cli(sys.argv[1:]))
