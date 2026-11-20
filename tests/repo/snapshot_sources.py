"""Spec 2.7 `::test_fixtures_are_synthetic`: where a test opens a snapshot, the path's source.

A static check of one test module's syntax tree (#599). A snapshot is opened by
`DataConfig(P)` or `DataConfig(path=P)`, `nexusbt`'s `open(P)` (or `open(path=P)`) under any
name it or `nexusbt.api` is imported as, a `snapshot=P` keyword (also inside `**{...}`), or
`tds check` given P: `nexusbt_tds`'s `check(P)`, or a command whose `"check"` is followed by
P (in a list, a tuple or a name bound to one) or written as one string. Each P is followed
back inside the module (names, `/` joins, subscripts, fixtures, helpers and every caller of a
helper called by its own name). It passes when it reaches, and only then, a call that writes
a synthetic package, each known by where the module imports it from (`WRITES`):

- `make_snapshot(root)` from `nexusbt.testing.synth`, not defined in the module: its package,
  written by the generator (4.8);
- `import_csv(mapping, out)` from `nexusbt_tds`, with `mapping` in the test's temporary folder
  (`tmp_path`, `mktemp`), so from files the test wrote: the package it returns;
- `shutil.copytree(src, dst)` with `src` synthetic: the copy it returns;
- a helper of the module that returns one;
- the paths inside one (`glob`, `rglob`, `iterdir`), or its `nx.open` snapshot.

Data roots and the conformance packages are #599's next part.

Any other call (`print`, `os.environ.get`, `os.path.join`, a method such as `.parent`)
gives no source. A path that starts from a string literal never passes, nor a join whose
right side is not a relative literal (or a name bound only to such): pathlib drops the left
side of an absolute one. What the trace cannot follow (a parameter no caller passes, a fixture
from another module) fails. Not followed: paths given through `nexusbt.toml` text,
`NEXUSBT_DATA_ROOT` or `--data-root`. A static check catches a path written by mistake, not
code written to get around it.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator

#: A literal that leaves the folder it is joined to, or names a place outside the test's.
ESCAPES = re.compile(r"^(/|~|[A-Za-z]:[\\/])|(^|[\\/])\.\.([\\/]|$)")
#: A literal after `"check"` that looks like a path rather than an option's value.
PATHLIKE = re.compile(r"[\\/~]|^\.")
#: A `tds check` command written as one string, and the calls that run such a string.
COMMAND = re.compile(r"(\btds|\bnexusbt_tds)\b.*\bcheck\s+\S")
RUNS = frozenset({"run", "call", "check_call", "check_output", "Popen", "system"})
#: Calls whose result lists the paths inside their first argument, or that folder's contents.
LISTS = frozenset({"sorted", "list", "tuple", "reversed"})
INSIDE = frozenset({"glob", "rglob", "iterdir"})
#: The calls that write a synthetic package: the module each comes from, and where its
#: destination is given (position, keyword).
WRITES = {
    "make_snapshot": ("nexusbt.testing.synth", 0, "root"),
    "import_csv": ("nexusbt_tds", 1, "out"),
    "copytree": ("shutil", 1, "dst"),
}
#: A trace that came back to one still being followed: it neither passes nor fails.
CYCLE = "cycle"

Function = ast.FunctionDef | ast.AsyncFunctionDef
Scope = Function | None
#: A source kind, None for a path not synthetic, or CYCLE.
Kind = str | None


def _name(call: ast.Call) -> str:
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def _arg(call: ast.Call, pos: int, key: str) -> ast.expr | None:
    found = next((k.value for k in call.keywords if k.arg == key), None)
    return call.args[pos] if found is None and pos < len(call.args) else found


def _imports(tree: ast.Module) -> dict[str, str]:
    """Each name the module imports, with the dotted name it stands for."""
    names = {"nx": "nexusbt", "nexusbt": "nexusbt", "nexusbt_tds": "nexusbt_tds"}
    names["shutil"] = "shutil"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                head = a.name.partition(".")[0]
                names[a.asname or head] = a.name if a.asname else head
        elif isinstance(node, ast.ImportFrom) and node.module:
            names |= {a.asname or a.name: f"{node.module}.{a.name}" for a in node.names}
    return names


def _is(call: ast.Call, names: dict[str, str], module: str, attr: str) -> bool:
    """`call` is `attr` of `module` (or of a module inside it), under the module's names."""
    head, dot, rest = ast.unparse(call.func).partition(".")
    full = names.get(head, head) + dot + rest
    return full.startswith(module + ".") and full.endswith("." + attr)


def _items(e: ast.expr, assigned: dict[str, list[ast.expr]]) -> list[ast.expr]:
    """A command's words: a list or tuple, or a name bound once to one in the module."""
    if isinstance(e, ast.Name) and len(assigned.get(e.id, [])) == 1:
        e = assigned[e.id][0]
    return list(e.elts) if isinstance(e, ast.List | ast.Tuple) else [e]


def openings(tree: ast.Module) -> Iterator[tuple[ast.Call, ast.expr]]:
    """Each call that opens a snapshot, with the expression of the path it opens."""
    names, assigned = _imports(tree), dict[str, list[ast.expr]]()
    for bind in (b for b in ast.walk(tree) if isinstance(b, ast.Assign)):
        for t in (t for t in bind.targets if isinstance(t, ast.Name)):
            assigned.setdefault(t.id, []).append(bind.value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        config, opens = _name(node) == "DataConfig", _is(node, names, "nexusbt", "open")
        named = [(k.arg, k.value) for k in node.keywords if k.arg]
        for k in node.keywords:  # `**{"snapshot": P}`
            if k.arg is None and isinstance(d := k.value, ast.Dict):
                named += [(c.value, v) for c, v in zip(d.keys, d.values, strict=True)
                          if isinstance(c, ast.Constant) and isinstance(c.value, str)]  # fmt: skip
        paths = ("path",) if config or opens else ()
        yield from ((node, v) for k, v in named if k == "snapshot" or k in paths)
        checks = _is(node, names, "nexusbt_tds", "check")
        if node.args and (config or opens or checks):
            yield node, node.args[0]
        lists = [_items(a, assigned) for a in [*node.args, *(v for k, v in named if k == "args")]]
        for words in [node.args, *lists]:  # `"check"` and its path in one list, or one call
            for n, w in enumerate(words):
                after = words[n + 1 :] if isinstance(w, ast.Constant) and w.value == "check" else []
                for a in after:  # the path, not the options and their values
                    if not isinstance(a, ast.Constant) or PATHLIKE.search(str(a.value)):
                        yield node, a
                        break
        for w in (w for words in lists for w in words if _name(node) in RUNS):
            if isinstance(w, ast.Constant | ast.JoinedStr | ast.BinOp):
                yield from [(node, w)] if COMMAND.search(ast.unparse(w)) else []


def _chain(e: ast.expr) -> Iterator[ast.expr]:
    """`e`, then what it is joined to, down to where it starts."""
    while True:
        yield e
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Div):
            e = e.left
        elif isinstance(e, ast.Subscript):
            e = e.value
        elif isinstance(e, ast.Call) and _name(e) in {"str", "Path"} and len(e.args) == 1:
            e = e.args[0]
        else:
            return


def _literal(e: ast.expr) -> bool:
    """`e` starts from a string literal."""
    return isinstance([*_chain(e)][-1], ast.Constant | ast.JoinedStr)


def _safe(e: ast.expr) -> bool:
    """A relative literal that stays inside the folder it is joined to."""
    if isinstance(e, ast.JoinedStr):  # its fixed text; it must start with some
        first = e.values[0] if e.values else None
        texts = [v.value for v in e.values if isinstance(v, ast.Constant)]
        return isinstance(first, ast.Constant) and all(_safe(ast.Constant(t)) for t in texts)
    return isinstance(e, ast.Constant) and isinstance(e.value, str) and not ESCAPES.search(e.value)


def _all(kinds: Iterable[Kind]) -> Kind:
    """Every one synthetic (a cycle aside): the first kind; None when one is not or none is."""
    found = list(kinds)
    if None in found:
        return None
    good = [k for k in found if k != CYCLE]
    return good[0] if good else (CYCLE if found else None)


def _good(kind: Kind) -> bool:
    return kind is not None and kind != CYCLE


def _returned(fn: ast.AST) -> Iterator[ast.expr]:
    """What `fn` returns or yields, not what a function inside it does."""
    for node in ast.iter_child_nodes(fn):
        if isinstance(node, ast.Return | ast.Yield) and node.value is not None:
            yield node.value
        if not isinstance(node, Function | ast.Lambda | ast.ClassDef):
            yield from _returned(node)


def _empty(e: ast.expr) -> bool:
    """`e` is an empty list, tuple, set or dict, written as one."""
    items = e.keys if isinstance(e, ast.Dict) else getattr(e, "elts", None)
    return isinstance(e, ast.List | ast.Tuple | ast.Set | ast.Dict) and not items


def _bound(name: str, target: ast.expr, value: ast.expr) -> Iterator[ast.expr]:
    """What binding `target` to `value` binds `name` to; `name[...] = value` counts."""
    if isinstance(target, ast.Subscript):
        target = target.value
    if isinstance(target, ast.Name) and target.id == name:
        yield value
    elif isinstance(target, ast.Tuple | ast.List):
        pairs = isinstance(value, ast.Tuple | ast.List) and len(value.elts) == len(target.elts)
        elts = value.elts if isinstance(value, ast.Tuple | ast.List) and pairs else None
        for i, el in enumerate(target.elts):
            if isinstance(el, ast.Name) and el.id == name:
                yield elts[i] if elts else value


def _values(name: str, fn: Function) -> list[ast.expr]:
    """Every expression `fn` binds `name` to; a loop's target, to each item of what it loops
    over (each item's part in that place, when the target is a tuple)."""
    values: list[ast.expr] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            values += [v for t in node.targets for v in _bound(name, t, node.value)]
        elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and node.value is not None:
            values += _bound(name, node.target, node.value)
        elif isinstance(node, ast.For | ast.comprehension):
            items = node.iter.elts if isinstance(node.iter, ast.List | ast.Tuple) else None
            values += [v for x in items or [node.iter] for v in _bound(name, node.target, x)]
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            values += _bound(name, node.optional_vars, node.context_expr)
    return values


def _params(fn: Function) -> list[str]:
    return [p.arg for p in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]]


class Trace:
    """Where the paths of one module come from."""

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.funcs = {n.name: n for n in tree.body if isinstance(n, Function)}
        self.names = _imports(tree)
        self.scope: dict[int, Function] = {}  # a node → the function it is in
        self._nest(tree, None)
        self.memo: dict[tuple[int, int], Kind] = {}
        self.following: set[tuple[int, int]] = set()
        self.cycles = 0

    def _nest(self, node: ast.AST, around: Scope) -> None:
        for child in ast.iter_child_nodes(node):
            if around is not None:
                self.scope[id(child)] = around
            self._nest(child, child if isinstance(child, Function) else around)

    def opened(self, path: ast.expr, call: ast.Call) -> bool:
        """The path a snapshot is opened from comes from a synthetic source."""
        return _good(self.source(path, self.scope.get(id(call))))

    def source(self, e: ast.expr, fn: Scope) -> Kind:
        key = (id(e), id(fn))
        if key in self.memo:
            return self.memo[key]
        if key in self.following:
            self.cycles += 1
            return CYCLE
        self.following.add(key)
        before = self.cycles
        kind = None if _literal(e) else self._source(e, fn)
        self.following.discard(key)
        if self.cycles == before:  # one cut short by a cycle is followed again from elsewhere
            self.memo[key] = kind
        return kind

    def _source(self, e: ast.expr, fn: Scope) -> Kind:
        if isinstance(e, ast.Call):
            return self._call(e, fn)
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Div):
            return self.source(e.left, fn) if self.part(e.right, fn) else None
        if isinstance(e, ast.Subscript | ast.Starred):
            return self.source(e.value, fn)
        if isinstance(e, ast.List | ast.Tuple | ast.Set | ast.Dict):
            items = e.values if isinstance(e, ast.Dict) else e.elts
            return _all(self.source(x, fn) for x in items) if items else CYCLE  # empty: no say
        if isinstance(e, ast.Name):
            return self._name_source(e, fn)
        return None  # an attribute such as `.parent`, `+`, anything else

    def part(self, e: ast.expr, fn: Scope, depth: int = 0) -> bool:
        """`e`, joined to a path, stays inside it: a relative literal, or a name every binding
        or caller gives such a literal."""
        if _safe(e) or not isinstance(e, ast.Name) or depth > len(self.funcs) + 8:
            return _safe(e)
        scope = fn
        while scope is not None and not (_values(e.id, scope) or e.id in _params(scope)):
            scope = self.scope.get(id(scope))
        if scope is None:
            values = [v for n in self.tree.body if isinstance(n, ast.Assign)
                      for t in n.targets for v in _bound(e.id, t, n.value)]  # fmt: skip
            return bool(values) and all(self.part(v, None, depth + 1) for v in values)
        given: list[tuple[ast.expr, Scope]] = [(v, scope) for v in _values(e.id, scope)]
        if e.id in _params(scope):  # what each caller gives, followed where it is given
            pos, calls = _params(scope).index(e.id), self._calls(scope.name)
            given += [(g, self.scope.get(id(c))) for c in calls
                      if (g := _arg(c, pos, e.id)) is not None]  # fmt: skip
            if not calls or e.id in self.funcs:
                return False
        return bool(given) and all(self.part(v, at, depth + 1) for v, at in given)

    def _calls(self, name: str) -> list[ast.Call]:
        """The calls of the module's function `name` by its bare name."""
        return [
            c
            for c in ast.walk(self.tree)
            if isinstance(c, ast.Call) and ast.unparse(c.func) == name
        ]

    def _call(self, e: ast.Call, fn: Scope) -> Kind:
        name = _name(e)
        if e.args and (name in {"str", "Path", *LISTS} or _is(e, self.names, "nexusbt", "open")):
            return self.source(e.args[0], fn)  # the same path, a list of them, or its snapshot
        if isinstance(e.func, ast.Attribute) and name in INSIDE:
            return self.source(e.func.value, fn)  # the paths inside a synthetic folder
        helper = self.funcs.get(name) if isinstance(e.func, ast.Name) else None
        if helper is not None:  # the module's own: judged by what it returns
            return _all(self.source(r, helper) for r in _returned(helper))
        return self._writer(e) if self._writes(e, fn) is not None else None

    def _writer(self, call: ast.Call) -> str | None:
        return next((w for w, (m, *_) in WRITES.items() if _is(call, self.names, m, w)), None)

    def _writes(self, call: ast.Call, fn: Scope) -> ast.expr | None:
        """Where `call`, one of `WRITES`, writes a synthetic package; None when it does not."""
        writer = self._writer(call)
        dest = None if writer is None else _arg(call, *WRITES[writer][1:])
        if dest is None or _literal(dest):
            return None
        if writer == "import_csv":
            mapping = _arg(call, 0, "mapping")
            return dest if mapping is not None and self._temporary(mapping, fn) else None
        source = _arg(call, 0, "src")
        synthetic = source is not None and _good(self.source(source, fn))
        return dest if writer == "make_snapshot" or synthetic else None

    def _temporary(self, e: ast.expr, fn: Scope, depth: int = 0) -> bool:
        """`e` lies in pytest's temporary folder for the test (`tmp_path`, `mktemp`), as every
        binding of it, or every caller that gives it, says."""
        base = [*_chain(e)][-1]
        if isinstance(base, ast.Call):
            return _name(base) == "mktemp"
        if fn is None or not isinstance(base, ast.Name) or depth > len(self.funcs) + 8:
            return False
        params = _params(fn)
        if base.id == "tmp_path" and base.id in params:
            return True
        given: list[tuple[ast.expr, Scope]] = [
            (v, fn) for v in _values(base.id, fn) if not _empty(v)
        ]
        if base.id in params and base.id not in self.funcs:
            pos = params.index(base.id)
            given += [(g, self.scope.get(id(c))) for c in self._calls(fn.name)
                      if (g := _arg(c, pos, base.id)) is not None]  # fmt: skip
        return bool(given) and all(self._temporary(v, at, depth + 1) for v, at in given)

    def _name_source(self, e: ast.Name, fn: Scope) -> Kind:
        scope = fn
        while scope is not None:  # the function, then the ones around it
            values, params = _values(e.id, scope), _params(scope)
            if values or e.id in params:
                if any(_literal(v) for v in values):
                    return None
                kinds = [self.source(v, scope) for v in values]
                if e.id in params:
                    kinds.append(self._param(e.id, params.index(e.id), scope))
                return _all(kinds)
            scope = self.scope.get(id(scope))
        values = [v for n in self.tree.body if isinstance(n, ast.Assign) for t in n.targets
                  for v in _bound(e.id, t, n.value)]  # fmt: skip
        return _all(self.source(v, None) for v in values)

    def _param(self, name: str, pos: int, fn: Function) -> Kind:
        if name in self.funcs:  # a fixture of this module
            return self._call(ast.Call(func=ast.Name(id=name), args=[], keywords=[]), None)
        passed = [(c, _arg(c, pos, name)) for c in self._calls(fn.name)]
        return _all(self.source(g, self.scope.get(id(c))) for c, g in passed if g is not None)


def findings(name: str, text: str) -> list[str]:
    """`file:line` for each snapshot this module opens from a path not traced to a source."""
    tree = ast.parse(text)
    trace = Trace(tree)
    return [
        f"{name}:{call.lineno}: snapshot path `{ast.unparse(path)}` not from a synthetic source"
        for call, path in openings(tree)
        if not trace.opened(path, call)
    ]
