"""Which files import which, for JavaScript, TypeScript and Python, read with regular expressions.

It finds the files that depend on an edited file (its blast radius). It is not a full parser:
dynamic paths and aliases other than '@/' and '~/' are not resolved.
"""
from __future__ import annotations

import os
import posixpath
import re

JS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte")
JS_SPEC = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|^\s*import\s+)['"]([^'"\n]+)['"]""", re.M)
PY_SPEC = re.compile(r"^\s*(?:from\s+([.\w]+)\s+import\s+\(?([\w ,]+)|import\s+([\w.]+))", re.M)
MAX_BYTES = 300_000
_cache = {}  # (path, mtime) -> specifiers


def specifiers(path, text):
    if path.endswith(".py"):
        out = []
        for module, names, plain in PY_SPEC.findall(text):
            if plain:
                out.append(plain)
            else:  # "from pkg import a, b as c": each name may be a module of pkg
                out += [f"{module}|{n.split()[0]}" for n in names.split(",") if n.strip()]
        return out
    return JS_SPEC.findall(text)


def _js_target(spec, src, files):
    if spec.startswith((".", "/")):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(src), spec))
    elif spec.startswith(("@/", "~/")):
        rest = spec[2:]
        base = next((p for p in (f"src/{rest}", rest) if any(f.startswith(p) for f in files)), rest)
    else:
        return None  # a package from node_modules
    for candidate in (base, *(base + e for e in JS), *(f"{base}/index{e}" for e in JS)):
        if candidate in files:
            return candidate
    return None


def _py_target(spec, src, files):
    if "|" in spec:  # from pkg import name: the module pkg.name if it exists, else pkg itself
        module, name = spec.split("|", 1)
        return _py_target(f"{module.rstrip('.')}.{name}" if module.strip(".") else module + name, src, files) \
            or (_py_target(module, src, files) if module.strip(".") else None)
    dots = len(spec) - len(spec.lstrip("."))
    parts = [p for p in spec.lstrip(".").split(".") if p]
    if dots:
        folder = posixpath.dirname(src)
        for _ in range(dots - 1):
            folder = posixpath.dirname(folder)
        bases = [posixpath.join(folder, *parts)]
    else:
        bases = [posixpath.join(*parts), posixpath.join("src", *parts)] if parts else []
    for base in bases:
        for candidate in (f"{base}.py", f"{base}/__init__.py"):
            if candidate in files:
                return candidate
    return None


def _read_specs(root, rel):
    full = os.path.join(root, rel)
    try:
        stat = os.stat(full)
        if stat.st_size > MAX_BYTES:
            return []
        key = (full, stat.st_mtime)
        if key not in _cache:
            with open(full, errors="replace") as f:
                _cache[key] = specifiers(rel, f.read())
        return _cache[key]
    except OSError:
        return []


def importers(root, files):
    """{file: [files that import it]} for the repo files given as paths relative to root."""
    known = set(files)
    index = {}
    for src in files:
        if src.endswith(".py"):
            resolve = _py_target
        elif src.endswith(JS):
            resolve = _js_target
        else:
            continue
        for spec in _read_specs(root, src):
            target = resolve(spec, src, known)
            if target and target != src:
                index.setdefault(target, [])
                if src not in index[target]:
                    index[target].append(src)
    return index
