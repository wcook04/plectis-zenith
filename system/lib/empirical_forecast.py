"""A declared empirical control inside the native graph, never a causal claim.

The first supported operator is deliberately narrow. It applies a frozen scale
and cap to the arithmetic mean of trailing simple returns. It does not select
parameters, learn weights, fetch data or establish predictive value.
"""
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import re


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def rule_errors(payload):
    if payload.get('forecast_basis','CAUSAL') != 'CAUSAL' or 'empirical_rule' in payload:
        return ['INVALID_FORECAST_BASIS: generic native graph supports CAUSAL observations only']
    return []


def target_errors(payload, subject_run_dir, issue_at, target_at):
    return []  # CP2 target/time/unit binding is owned by the shared validator.
