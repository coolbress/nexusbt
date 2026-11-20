"""Spec 2.7 `::test_fixtures_are_synthetic`: where a test opens a snapshot, the path's source.

A static check of one test module's syntax tree (#599). A snapshot is opened by
`DataConfig(P)` or `DataConfig(path=P)`, `nexusbt`'s `open(P)` (or `open(path=P)`) under any
name it or `nexusbt.api` is imported as, or a `snapshot=P` keyword (also inside `**{...}`).
Each P is followed back inside the module (names, `/` joins, subscripts, fixtures, helpers
and every caller of a helper called by its own name). It passes when it reaches, and only
then:

- `make_snapshot(root)`, imported from `nexusbt.testing.synth` and not defined in the module:
  its package, written by the generator (4.8);
- a helper of the module that returns one, or its `nx.open` snapshot.

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
#: Where the generator comes from.
SYNTH = "nexusbt.testing.synth"
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


def _imports(tree: ast.Module) -> dict[str, set[str]]:
    """What the module calls `nexusbt` (or its `api`), its `open` and the generator (as a
    name, or the module it is reached through)."""
    found: dict[str, set[str]] = {"modules": {"nx", "nexusbt"}, "open": set(), "synth": set()}
    found["synth_modules"] = set()
    names = {"open": "open", "make_snapshot": "synth", "api": "modules"}
    what = {"nexusbt": {"open", "api"}, "nexusbt.api": {"open"}, SYNTH: {"make_snapshot"}}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            key = {"nexusbt": "modules", "nexusbt.api": "modules", SYNTH: "synth_modules"}
            for a in (a for a in node.names if a.name in key):
                found[key[a.name]].add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and node.module in what:
            for a in (a for a in node.names if a.name in what[node.module]):
                found[names[a.name]].add(a.asname or a.name)
    return found


def _called(call: ast.Call, names: set[str], modules: set[str], attr: str) -> bool:
    """`call` is `attr` under one of `names`, or `<one of modules>.attr`."""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id in names
    return isinstance(f, ast.Attribute) and f.attr == attr and ast.unparse(f.value) in modules


def openings(tree: ast.Module) -> Iterator[tuple[ast.Call, ast.expr]]:
    """Each call that opens a snapshot, with the expression of the path it opens."""
    i = _imports(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        config, opens = _name(node) == "DataConfig", _called(node, i["open"], i["modules"], "open")
        named = [(k.arg, k.value) for k in node.keywords if k.arg]
        for k in node.keywords:  # `**{"snapshot": P}`
            if k.arg is None and isinstance(d := k.value, ast.Dict):
                named += [(c.value, v) for c, v in zip(d.keys, d.values, strict=True)
                          if isinstance(c, ast.Constant) and isinstance(c.value, str)]  # fmt: skip
        paths = ("path",) if config or opens else ()
        yield from ((node, v) for k, v in named if k == "snapshot" or k in paths)
        if node.args and (config or opens):
            yield node, node.args[0]


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


def _bound(name: str, target: ast.expr, value: ast.expr) -> Iterator[ast.expr]:
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
        self.imports = _imports(tree)
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
            return _all(self.source(x, fn) for x in items)
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
        name, i = _name(e), self.imports
        if e.args and (name in {"str", "Path"} or _called(e, i["open"], i["modules"], "open")):
            return self.source(e.args[0], fn)  # the same path, or its snapshot
        helper = self.funcs.get(name) if isinstance(e.func, ast.Name) else None
        if helper is not None:  # the module's own: judged by what it returns
            return _all(self.source(r, helper) for r in _returned(helper))
        if _called(e, i["synth"], i["synth_modules"], "make_snapshot"):
            root = _arg(e, 0, "root")
            return "make_snapshot" if root is not None and not _literal(root) else None
        return None

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
