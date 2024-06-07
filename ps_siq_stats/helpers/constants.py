#!/usr/bin/env python
# -*- coding: utf8 -*-
# fmt: off
__license__       = "MIT"
__author__        = "Andrew Chung <andrew.chung@dell.com>"
__maintainer__    = "Andrew Chung <andrew.chung@dell.com>"
__email__         = "andrew.chung@dell.com"
__all__ = [
    "parse",
]
# fmt: on
DEFAULT_SERVER_PORT = 8000
PROGRAM_NAME = "ps_siq_stats"
STR_MISSING_MODULE_PROMETHEUS = """Could not load Prometheus Python modules. Please check if the modules are
available or install the modules with:
pip install prometheus-client
"""
STR_MISSING_MODULE_YAML = """Could not load the yaml Python module. Please check if the module is
available or install the module with:
pip install yaml
"""
