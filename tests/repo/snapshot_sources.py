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
  (`tmp_path`, `mktemp`): its package, written into `out` (what the mapping names is not
  read);
- `shutil.copytree(src, dst)` with `src` synthetic: a copy, written into `dst`;
- a helper of the module that returns one, or writes one into a folder it is given;
- a folder one of these wrote into (a data root) or a path inside it; a folder above such
  folders only inside the test's temporary folder, and from it only the way down to them;
- the paths inside one (`glob`, `rglob`, `iterdir`), or its `nx.open` snapshot;
- a package under `tds/conformance/` reached from the repository root (`Path(__file__)` taken
  up exactly to it), while `GUARD` rebuilds those packages with `build.build` and asserts;
- in `PARITY_TEST` alone, `manifest["snapshot"]` from its fixture reading the runner's
  `OUT / "manifest.json"`, while `RUNNER` names there only what it wrote with the generator's
  command (`runner_writes_synth`).

What it reads is the code: how each path is built, not what a file holds. It does not read
what a mapping file names or what a test copies into a data root; these, and the ways past it
listed in #630, are its known limits.

The memos (`Trace`'s `remember`) only keep the check fast; they change no verdict.

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
import json
import re
from collections.abc import Callable, Iterable, Iterator
from typing import Any, TypeVar, cast

T = TypeVar("T")

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
#: Where the conformance packages are shown to be `tds/conformance/build.py`'s output (2.7).
GUARD = ("tds/tests/test_cli.py", "test_committed_packages_match_the_generator")
#: A trace that came back to one still being followed: it neither passes nor fails.
CYCLE = "cycle"
#: The kind of a folder above packages, followed by the way down to each, as JSON.
ABOVE = "above:"

Function = ast.FunctionDef | ast.AsyncFunctionDef
Scope = Function | None
#: A source kind, None for a path not synthetic, or CYCLE.
Kind = str | None
#: A path as where it starts, then each part joined to it (`*` when not a literal).
Parts = tuple[str, ...]
#: A folder a call may write a package into, that call, and the function it is in.
Dest = tuple[Parts, ast.Call, Scope]


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


def _parts(e: ast.expr) -> Parts:
    chain = [*_chain(e)]
    joined = [c.right if isinstance(c, ast.BinOp) else c.slice for c in chain[:-1]
              if isinstance(c, ast.BinOp | ast.Subscript)]  # fmt: skip
    texts = [p.value if isinstance(p, ast.Constant) and isinstance(p.value, str) else "*"
             for p in reversed(joined)]  # fmt: skip
    return (ast.dump(chain[-1]), *texts)


def _within(a: Parts, b: Parts) -> bool:
    """`b` is `a` or lies in it (`*` stands for any one part)."""
    return len(a) <= len(b) and all(x == y or "*" in (x, y) for x, y in zip(a, b, strict=False))


def _step(above: str, part: str) -> Kind:
    """One part down from a folder above packages: into one ("root"), still above some, or
    beside them all (None)."""
    down = [tuple(d) for d in json.loads(above.removeprefix(ABOVE))]
    if any(d[:1] == (part,) or d[:1] == ("*",) or part == "*" for d in down if len(d) == 1):
        return "root"
    rest = [d[1:] for d in down if len(d) > 1 and _within(d[:1], (part,))]
    return ABOVE + json.dumps(rest) if rest else None


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


def _roots(name: str) -> set[str]:
    """The repository, as the file `name` writes it: `Path(__file__)` taken up exactly to it."""
    up = len(name.split("/"))  # `tests/x.py`: the repository is `Path(__file__).parents[1]`
    forms = (f".parents[{up - 1}]", ".parent" * up)
    return {f"Path(__file__){r}{f}" for r in ("", ".resolve()") for f in forms}


def _module_value(tree: ast.Module, name: str) -> ast.expr | None:
    """What the module binds `name` to at its top level, when it binds it once."""
    found = [v for n in tree.body if isinstance(n, ast.Assign)
             for t in n.targets for v in _bound(name, t, n.value)]  # fmt: skip
    return found[0] if len(found) == 1 else None


def _params(fn: Function) -> list[str]:
    return [p.arg for p in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]]


class Trace:
    """Where the paths of one module come from; `conformance` when `GUARD` holds. With
    `remember`, the reads below are kept (`kept`) and the data roots found (`rooted`)."""

    def __init__(
        self, tree: ast.Module, name: str = "", conformance: bool = False, remember: bool = True
    ) -> None:
        self.tree = tree
        self.funcs = {n.name: n for n in tree.body if isinstance(n, Function)}
        self.names = _imports(tree)
        self.roots = _roots(name) if conformance else set()
        self.scope: dict[int, Function] = {}  # a node → the function it is in
        self._nest(tree, None)
        self.memo: dict[tuple[int, int], Kind] = {}
        self.remember, self.kept, self.rooted = remember, dict[object, Any](), dict[object, Kind]()
        self.following: set[tuple[int, int]] = set()
        self.cycles = 0

    def _keep(self, key: object, make: Callable[[], T]) -> T:
        """`make()`, kept under `key` when the trace remembers."""
        if key in self.kept:
            return cast("T", self.kept[key])
        value = make()
        if self.remember:
            self.kept[key] = value
        return value

    def bound(self, name: str, fn: Function) -> list[ast.expr]:
        return self._keep(("bound", name, id(fn)), lambda: _values(name, fn))

    def _calls_in(self, fn: Function) -> list[ast.Call]:
        return self._keep(
            ("calls in", id(fn)), lambda: [c for c in ast.walk(fn) if isinstance(c, ast.Call)]
        )

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
        if isinstance(e, ast.BinOp | ast.Subscript):
            if isinstance(e, ast.BinOp) and not (
                isinstance(e.op, ast.Div) and self.part(e.right, fn)
            ):
                return None
            if self._conformance(e, fn):
                return "conformance"
            inner = self.source(e.left if isinstance(e, ast.BinOp) else e.value, fn)
            if inner and inner.startswith(ABOVE):  # a step down from a folder above packages
                inner = _step(inner, _parts(e)[-1])
            return inner if _good(inner) else self._root(e, fn) or inner
        if isinstance(e, ast.Starred):
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
        while scope is not None and not (self.bound(e.id, scope) or e.id in _params(scope)):
            scope = self.scope.get(id(scope))
        if scope is None:
            values = self._module_values(e.id)
            return bool(values) and all(self.part(v, None, depth + 1) for v in values)
        given: list[tuple[ast.expr, Scope]] = [(v, scope) for v in self.bound(e.id, scope)]
        if e.id in _params(scope):  # what each caller gives, followed where it is given
            pos, calls = _params(scope).index(e.id), self._calls(scope.name)
            given += [(g, self.scope.get(id(c))) for c in calls
                      if (g := _arg(c, pos, e.id)) is not None]  # fmt: skip
            if not calls or e.id in self.funcs:
                return False
        return bool(given) and all(self.part(v, at, depth + 1) for v, at in given)

    def _module_values(self, name: str) -> list[ast.expr]:
        """What the module binds `name` to at its top level."""
        return [v for n in self.tree.body if isinstance(n, ast.Assign)
                for t in n.targets for v in _bound(name, t, n.value)]  # fmt: skip

    def _inside(self, e: ast.expr, fn: Scope) -> bool:
        """Every join in `e` stays inside the folder it is joined to."""
        return all(self.part(c.right, fn) for c in _chain(e) if isinstance(c, ast.BinOp))

    def _calls(self, name: str) -> list[ast.Call]:
        """The calls of the module's function `name` by its bare name."""
        return self._keep(
            ("calls of", name),
            lambda: [c for c in self._calls_in_module() if ast.unparse(c.func) == name],
        )

    def _calls_in_module(self) -> list[ast.Call]:
        return self._keep(
            "calls", lambda: [c for c in ast.walk(self.tree) if isinstance(c, ast.Call)]
        )

    def _call(self, e: ast.Call, fn: Scope) -> Kind:
        name = _name(e)
        if e.args and (name in {"str", "Path", *LISTS} or _is(e, self.names, "nexusbt", "open")):
            return self.source(e.args[0], fn)  # the same path, a list of them, or its snapshot
        if isinstance(e.func, ast.Attribute) and name in INSIDE:
            return self.source(e.func.value, fn)  # the paths inside a synthetic folder
        helper = self.funcs.get(name) if isinstance(e.func, ast.Name) else None
        if helper is not None:  # the module's own: judged by what it returns
            returned = self._keep(("returned", id(helper)), lambda: list(_returned(helper)))
            return _all(self.source(r, helper) for r in returned)
        return self._writer(e) if self._writes(e, fn) is not None else None

    def _writer(self, call: ast.Call) -> str | None:
        found = (w for w, (m, *_) in WRITES.items() if _is(call, self.names, m, w))
        return self._keep(("writer", id(call)), lambda: next(found, None))

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
            (v, fn) for v in self.bound(base.id, fn) if not _empty(v)
        ]
        if base.id in params and base.id not in self.funcs:
            pos = params.index(base.id)
            given += [(g, self.scope.get(id(c))) for c in self._calls(fn.name)
                      if (g := _arg(c, pos, base.id)) is not None]  # fmt: skip
        return bool(given) and all(self._temporary(v, at, depth + 1) for v, at in given)

    def _dests(self, call: ast.Call, fn: Scope, seen: frozenset[str] = frozenset()) -> list[Dest]:
        """Where `call` may write a package, by the code's shape alone: each folder, with the
        call of `WRITES` that writes it and the function that call is in."""
        return self._keep(("dests", id(call), id(fn), seen), lambda: self._dests_of(call, fn, seen))

    def _dests_of(self, call: ast.Call, fn: Scope, seen: frozenset[str]) -> list[Dest]:
        writer = self._writer(call)
        dest = None if writer is None else _arg(call, *WRITES[writer][1:])
        if dest is not None:
            return (
                [] if _literal(dest) or not self._inside(dest, fn) else [(_parts(dest), call, fn)]
            )
        name = _name(call)
        helper = self.funcs.get(name) if isinstance(call.func, ast.Name) else None
        if helper is None or name in seen:
            return []
        inner = [d for c in self._calls_in(helper) for d in self._dests(c, helper, seen | {name})]
        out = []
        for i, p in enumerate(_params(helper)):  # a folder the helper writes into, given here
            given = _arg(call, i, p)
            if given is None or _literal(given) or not self._inside(given, fn):
                continue
            mark = ast.dump(ast.Name(id=p, ctx=ast.Load()))
            out += [(_parts(given) + d[1:], c, at) for d, c, at in inner if d[0] == mark]
        return out

    def _root(self, e: ast.expr, fn: Scope) -> Kind:
        """`e` is a folder `fn` wrote a synthetic package into or a path inside it ("root"),
        or, in the test's temporary folder, a folder above such folders (`ABOVE`)."""
        key, before = (id(e), id(fn)), self.cycles
        if key in self.rooted:
            return self.rooted[key]
        kind = self._root_of(e, fn)
        if self.remember and self.cycles == before:  # one cut short by a cycle: not kept
            self.rooted[key] = kind
        return kind

    def _root_of(self, e: ast.expr, fn: Scope) -> Kind:
        if fn is None or _literal(e) or not self._inside(e, fn):
            return None
        path, down = _parts(e), []
        for call in self._calls_in(fn):
            for into, writes, at in self._dests(call, fn):
                inside, above = _within(into, path), _within(path, into)
                if not (inside or above) or self._writes(writes, at) is None:
                    continue  # elsewhere, or not a synthetic package
                if inside:
                    return "root"
                down.append(into[len(path) :])
        return ABOVE + json.dumps(down) if down and self._temporary(e, fn) else None

    def _conformance(self, e: ast.expr, fn: Scope) -> bool:
        """`e` is `<the repository> / "tds" / "conformance" / ...`, with the repository written
        as `Path(__file__)` taken up exactly to it, directly or through one name."""
        if not self.roots or _parts(e)[1:3] != ("tds", "conformance") or not self._inside(e, fn):
            return False
        base = [*_chain(e)][-1]
        if isinstance(base, ast.Name):
            values = (self.bound(base.id, fn) if fn else []) or self._module_values(base.id)
            base = values[0] if len(values) == 1 else base
        return ast.unparse(base) in self.roots

    def _name_source(self, e: ast.Name, fn: Scope) -> Kind:
        scope = fn
        while scope is not None:  # the function, then the ones around it
            values, params = self.bound(e.id, scope), _params(scope)
            if values or e.id in params:
                if any(_literal(v) for v in values):
                    return None
                kinds = [self.source(v, scope) for v in values]
                if e.id in params:
                    kinds.append(self._param(e.id, params.index(e.id), scope))
                kind = _all(kinds)
                return kind if _good(kind) else self._root(e, scope) or kind
            scope = self.scope.get(id(scope))
        return _all(self.source(v, None) for v in self._module_values(e.id))

    def _param(self, name: str, pos: int, fn: Function) -> Kind:
        if name in self.funcs:  # a fixture of this module
            return self._call(ast.Call(func=ast.Name(id=name), args=[], keywords=[]), None)
        passed = [(c, _arg(c, pos, name)) for c in self._calls(fn.name)]
        return _all(self.source(g, self.scope.get(id(c))) for c, g in passed if g is not None)


def guard_holds(text: str) -> bool:
    """`GUARD`'s test is in `text`, rebuilds the packages with `build.build` and asserts."""
    test = next(
        (n for n in ast.parse(text).body if isinstance(n, Function) and n.name == GUARD[1]), None
    )
    nodes = list(ast.walk(test)) if test else []
    rebuilds = any(isinstance(n, ast.Call) and ast.unparse(n.func) == "build.build" for n in nodes)
    return rebuilds and any(isinstance(n, ast.Assert) for n in nodes)


#: 8.1's parity runner, which writes its package with the generator's command in another
#: process and names it in its manifest, and the one test module that opens that package.
RUNNER, PARITY_TEST = "tests/parity/parity/run.py", "tests/parity_compare/test_L1.py"


def _path_arg(e: ast.expr) -> str | None:
    """The name `e` is, or the name in `str(e)`."""
    if isinstance(e, ast.Call) and _name(e) == "str" and len(e.args) == 1:
        e = e.args[0]
    return e.id if isinstance(e, ast.Name) else None


def _writes_synth_to(fn: Function, name: str) -> bool:
    """`fn` runs `-m nexusbt.testing.synth ... --out <name>`."""
    for call in (c for c in ast.walk(fn) if isinstance(c, ast.Call)):
        words = [a.value if isinstance(a, ast.Constant) else a for a in call.args]
        if "-m" in words and "nexusbt.testing.synth" in words and "--out" in words[:-1]:
            given = words[words.index("--out") + 1]
            if isinstance(given, ast.expr) and _path_arg(given) == name:
                return True
    return False


def runner_writes_synth(runner: ast.Module) -> bool:
    """Every `"snapshot"` the runner records is the name a helper of its own returns, and that
    helper gave that name as `--out` to the generator's command (4.8)."""
    funcs = {n.name: n for n in runner.body if isinstance(n, Function)}
    recorded = [(fn, v) for fn in funcs.values() for d in ast.walk(fn) if isinstance(d, ast.Dict)
                for k, v in zip(d.keys, d.values, strict=True)
                if isinstance(k, ast.Constant) and k.value == "snapshot"]  # fmt: skip
    for fn, value in recorded:
        name = _path_arg(value)
        made = _values(name, fn) if name else []
        helpers = [h for m in made if isinstance(m, ast.Call) and (h := funcs.get(_name(m)))]
        if not made or len(helpers) != len(made):  # each made by a helper of the runner's own
            return False
        for helper in helpers:
            returned = [_path_arg(r) for r in _returned(helper)]
            if not returned or not all(r and _writes_synth_to(helper, r) for r in returned):
                return False
    return bool(recorded)


def _runner_out(runner: ast.Module) -> set[str]:
    """Where the runner writes its manifest by default: `--out`'s default under its `ROOT`,
    the repository, joined to each `--fixture` choice."""
    root, given = _module_value(runner, "ROOT"), dict[str, ast.Call]()
    for c in (
        c for c in ast.walk(runner) if isinstance(c, ast.Call) and _name(c) == "add_argument"
    ):
        given |= {str(a.value): c for a in c.args[:1] if isinstance(a, ast.Constant)}
    out = _arg(given["--out"], 99, "default") if "--out" in given else None
    choices = _arg(given["--fixture"], 99, "choices") if "--fixture" in given else None
    if root is None or ast.unparse(root) not in _roots(RUNNER) or out is None:
        return set()
    names = choices.elts if isinstance(choices, ast.List | ast.Tuple) else []
    return {f"{ast.unparse(out)} / {n.value!r}" for n in names if isinstance(n, ast.Constant)}


def _reads_manifest(tree: ast.Module, outs: set[str]) -> bool:
    """The module's `manifest` fixture returns only what `json.loads` reads from
    `OUT / "manifest.json"`, `OUT` being where the runner writes, under the repository."""
    fixture = next((n for n in tree.body if isinstance(n, Function) and n.name == "manifest"), None)
    out, root = _module_value(tree, "OUT"), _module_value(tree, "ROOT")
    if (
        fixture is None
        or out is None
        or root is None
        or ast.unparse(root) not in _roots(PARITY_TEST)
    ):
        return False
    fixed = any("fixture" in ast.unparse(d) for d in fixture.decorator_list)
    returned = list(_returned(fixture))
    loads = [
        v for r in returned for v in (_values(r.id, fixture) if isinstance(r, ast.Name) else [])
    ]
    return (
        fixed
        and bool(loads)
        and len(loads) == len(returned)
        and ast.unparse(out) in outs
        and all(_loads_manifest(v, fixture) for v in loads)
    )


def _loads_manifest(e: ast.expr, fixture: Function) -> bool:
    """`e` is `json.loads(path.read_text(...))`, `path` bound only to `OUT / "manifest.json"`."""
    if not (isinstance(e, ast.Call) and ast.unparse(e.func) == "json.loads" and e.args):
        return False
    read = e.args[0]
    if not (isinstance(read, ast.Call) and isinstance(f := read.func, ast.Attribute)):
        return False
    paths = _values(f.value.id, fixture) if isinstance(f.value, ast.Name) else []
    return f.attr == "read_text" and [ast.unparse(p) for p in paths] == ["OUT / 'manifest.json'"]


def findings(
    name: str, text: str, guard: str | None = None, remember: bool = True, runner: str | None = None
) -> list[str]:
    """`file:line` for each snapshot this module opens from a path not traced to a source;
    `guard` is the text of `GUARD`'s file, read for a conformance package, and `runner` that of
    `RUNNER`, read for `PARITY_TEST`'s `manifest["snapshot"]` alone."""
    tree = ast.parse(text)
    trace = Trace(tree, name, guard is not None and guard_holds(guard), remember)
    ran = ast.parse(runner) if name == PARITY_TEST and runner is not None else None
    parity = (
        ran is not None and runner_writes_synth(ran) and _reads_manifest(tree, _runner_out(ran))
    )

    def from_runner(path: ast.expr, call: ast.Call) -> bool:
        fn = trace.scope.get(id(call))
        return (
            parity and fn is not None and ast.unparse(path) == "manifest['snapshot']"
            and "manifest" in _params(fn) and not trace.bound("manifest", fn)
        )  # fmt: skip

    return [
        f"{name}:{call.lineno}: snapshot path `{ast.unparse(path)}` not from a synthetic source"
        for call, path in openings(tree)
        if not trace.opened(path, call) and not from_runner(path, call)
    ]
