"""Execute model-authored, bounded table investigations and preserve acquisition traces.

This is a deliberately restricted Python subset, not a general untrusted-code service.
No imports, ambient names, arbitrary attributes, file/network access or top-level effects.
Evaluation happens in a fresh resource-limited interpreter with an empty environment.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import threading

METHODS = frozenset('get items keys values append extend sort lower upper strip split setdefault add discard copy count index pop remove clear update'.split())
BUILTINS = {name: value for name, value in vars(__import__('builtins')).items()
            if name in 'abs all any bool dict enumerate float int isinstance len list max min range reversed round set sorted str sum tuple zip'.split()}
NODES = frozenset('Module FunctionDef arguments arg Return Assign AugAssign Delete Nonlocal Expr If For Break Continue Pass '
                  'Name Load Store Del Constant List Tuple Dict Set Subscript Slice Attribute Call keyword '
                  'BinOp UnaryOp BoolOp Compare IfExp ListComp SetComp DictComp GeneratorExp comprehension Lambda '
                  'Add Sub Mult Div FloorDiv Mod BitOr BitAnd BitXor UAdd USub Not And Or Eq NotEq Lt LtE Gt GtE In NotIn Is IsNot'.split())
JSON_ANSWER_MAX_BYTES = 60_000
JSON_ANSWER_MAX_DEPTH = 16


def validate_answer_contract(answer_contract):
    if answer_contract not in ('investigation', 'json'):
        raise ValueError("answer_contract must be 'investigation' or 'json'")


def validate_json_answer(answer):
    """Accept only finite JSON values within a byte and nesting envelope."""
    visited = 0

    def visit(value, depth):
        nonlocal visited
        visited += 1
        if depth > JSON_ANSWER_MAX_DEPTH:
            raise ValueError('JSON answer exceeds nesting depth limit')
        if visited > JSON_ANSWER_MAX_BYTES:
            raise ValueError('JSON answer exceeds serialized size limit')
        kind = type(value)
        if value is None or kind in (bool, int):
            return
        if kind is float:
            if not math.isfinite(value):
                raise ValueError('JSON numbers must be finite')
            return
        if kind is str:
            if len(value) > JSON_ANSWER_MAX_BYTES:
                raise ValueError('JSON answer exceeds serialized size limit')
            return
        if kind not in (dict, list):
            raise ValueError('answer must contain only JSON objects, arrays and scalars')
        if len(value) > JSON_ANSWER_MAX_BYTES:
            raise ValueError('JSON answer exceeds serialized size limit')
        if kind is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError('JSON object keys must be strings')
                visit(key, depth)
                visit(item, depth + 1)
        else:
            for item in value:
                visit(item, depth + 1)

    visit(answer, 0)
    size = 0
    encoder = json.JSONEncoder(allow_nan=False, separators=(',', ':'), ensure_ascii=True)
    for chunk in encoder.iterencode(answer):
        size += len(chunk.encode('utf8'))
        if size > JSON_ANSWER_MAX_BYTES:
            raise ValueError('JSON answer exceeds serialized size limit')
    return answer


def validate_source(source):
    if not isinstance(source, str) or len(source.encode()) > 60000:
        raise ValueError('program must be at most 60000 UTF8 bytes')
    tree = ast.parse(source)
    if not tree.body or any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError('only function definitions are permitted at top level')
    if 'investigate' not in [node.name for node in tree.body]:
        raise ValueError('define investigate(context, acquire)')
    nodes = list(ast.walk(tree))
    if len(nodes) > 8000:
        raise ValueError('program AST too large')
    for node in nodes:
        if type(node).__name__ not in NODES:
            raise ValueError(f'unsupported syntax: {type(node).__name__}')
        if isinstance(node, (ast.FunctionDef, ast.arg, ast.Name)):
            name = node.name if isinstance(node, ast.FunctionDef) else node.arg if isinstance(node, ast.arg) else node.id
            # A single underscore is an ordinary discard/local variable, not
            # access to an ambient or interpreter-private name.
            if name.startswith('_') and not (name == '_' and not isinstance(node, ast.FunctionDef)):
                raise ValueError('private names are not permitted')
        if isinstance(node, ast.Nonlocal) and any(name.startswith('_') for name in node.names):
            raise ValueError('private names are not permitted')
        if isinstance(node, ast.Delete):
            targets = list(node.targets)
            while targets:
                target = targets.pop()
                if isinstance(target, (ast.Tuple, ast.List)):
                    targets.extend(target.elts)
                elif not isinstance(target, (ast.Name, ast.Subscript)):
                    raise ValueError('deletion is permitted only for names and subscripts')
        if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.returns or node.args.defaults or node.args.kw_defaults):
            raise ValueError('decorators, annotations and function defaults are not permitted')
        if isinstance(node, ast.arg) and node.annotation:
            raise ValueError('annotations are not permitted')
        if isinstance(node, ast.Attribute) and node.attr not in METHODS:
            raise ValueError(f'unsupported method: {node.attr}')
    return tree


def validate_answer(answer, *, answer_contract='investigation'):
    validate_answer_contract(answer_contract)
    if answer_contract == 'json':
        return validate_json_answer(answer)
    if not isinstance(answer, dict) or set(answer) != {'findings', 'unresolved', 'ratio'}:
        raise ValueError('answer requires exactly findings, unresolved and ratio')
    for key in ('findings', 'unresolved'):
        value = answer[key]
        if not isinstance(value, list) or len(value) > 20 or any(not isinstance(x, str) or len(x) > 100 for x in value):
            raise ValueError('findings and unresolved must be bounded string lists')
        if len(value) != len(set(value)):
            raise ValueError('duplicate answer entries')
    ratio = answer['ratio']
    if ratio is not None and (type(ratio) not in (float, int) or not math.isfinite(ratio) or ratio < 0):
        raise ValueError('ratio must be finite nonnegative or null')
    return answer


def execute_local(source, cases, *, answer_contract='investigation'):
    """Worker-only execution; callers must use execute for process limits."""
    validate_answer_contract(answer_contract)
    code = compile(validate_source(source), '<investigation>', 'exec')
    results = []
    for case in cases:
        trace = []
        def acquire(table):
            if not isinstance(table, str) or table not in case['tables'] or len(trace) >= 8:
                raise ValueError('unknown table or acquisition limit exceeded')
            data = json.loads(json.dumps(case['tables'][table]))
            trace.append({'table': table, 'rows': len(data),
                          'sha256': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()})
            return data
        namespace = {'__builtins__': BUILTINS}
        try:
            exec(code, namespace)
            context = json.loads(json.dumps({k: v for k, v in case.items() if k not in ('tables', 'id')}))
            answer = validate_answer(namespace['investigate'](context, acquire), answer_contract=answer_contract)
            results.append({'answer': answer, 'trace': trace, 'error': None})
        except Exception as exc:
            results.append({'answer': None, 'trace': trace, 'error': f'{type(exc).__name__}: {exc}'[:500]})
    return results


def execute(source, cases, *, answer_contract='investigation'):
    validate_answer_contract(answer_contract)
    validate_source(source)
    request = json.dumps({'source': source, 'cases': cases, 'answer_contract': answer_contract}, allow_nan=False)
    if len(request.encode()) > 12_000_000:
        raise ValueError('evaluation batch exceeds 12 MB')
    process = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()), '--worker'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env={}, cwd='/')
    stopped = threading.Event()
    def watch_memory():
        # macOS does not implement a useful lower RLIMIT_AS for this interpreter.
        # Bound this child's resident set without touching any other process.
        while not stopped.wait(.1):
            try:
                check = subprocess.run(['/bin/ps', '-o', 'rss=', '-p', str(process.pid)], capture_output=True, text=True, timeout=1)
                if check.stdout.strip() and int(check.stdout.strip()) > 256 * 1024:
                    process.kill()
                    return
            except (ValueError, OSError, subprocess.TimeoutExpired):
                process.kill()
                return
    watcher = threading.Thread(target=watch_memory, daemon=True)
    watcher.start()
    try:
        stdout, stderr = process.communicate(request, timeout=30)
        if process.returncode:
            raise RuntimeError('program worker terminated: ' + stderr[-500:])
        return json.loads(stdout)
    except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as exc:
        if process.poll() is None:
            process.kill()
            process.communicate()
        return [{'answer': None, 'trace': [], 'error': str(exc)[:500]} for case in cases]
    finally:
        stopped.set()
        watcher.join(timeout=2)


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    if sys.platform != 'darwin':
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    payload = json.load(sys.stdin)
    print(json.dumps(execute_local(payload['source'], payload['cases'],
                                   answer_contract=payload.get('answer_contract', 'investigation')), allow_nan=False))
