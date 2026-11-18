# Additional patch pairs (disjoint from the first 15)


## X01 BASE | sympy__sympy-15599 | code-review-and-quality | changed=10

```diff
diff --git a/sympy/core/mod.py b/sympy/core/mod.py
index eae25630c..2fb5f9673 100644
--- a/sympy/core/mod.py
+++ b/sympy/core/mod.py
@@ -167,6 +167,12 @@ def doit(p, q):
             # e.g. Mod(.6*x, .3*y) -> 0.3*Mod(2*x, y)
             cp, p = p.as_coeff_Mul()
             cq, q = q.as_coeff_Mul()
+            # reduce the coefficient modulo an integer modulus when the
+            # remaining factor is known to be an integer and contains no
+            # Mod, e.g. Mod(3*i, 2) -> Mod(i, 2)
+            if (qwas.is_Integer and not p.has(cls) and
+                    p.is_integer and cp.is_Integer):
+                cp = cp % qwas
             ok = False
             if not cp.is_Rational or not cq.is_Rational:
                 r = cp % cq
```

## X01 SKILL | sympy__sympy-15599 | code-review-and-quality | changed=10

```diff
diff --git a/sympy/core/mod.py b/sympy/core/mod.py
index eae25630c..2ed8cdb25 100644
--- a/sympy/core/mod.py
+++ b/sympy/core/mod.py
@@ -57,6 +57,16 @@ def doit(p, q):
                 if rv is not None:
                     return rv
 
+            # For an integer product c*m with an integer modulus q,
+            # reduce the numeric coefficient modulo q:
+            # Mod(c*m, q) == Mod((c % q)*m, q).
+            if isinstance(p, Mul) and q.is_Integer and p.is_integer:
+                c, m = p.as_coeff_Mul()
+                if c.is_Integer and m.is_integer:
+                    r = c % q
+                    if r != c:
+                        return cls(r*m, q)
+
             # by ratio
             r = p/q
             try:
```

---


## X02 BASE | sympy__sympy-13031 | test-driven-development | changed=12

```diff
diff --git a/sympy/matrices/sparse.py b/sympy/matrices/sparse.py
index e6f36cdf3..ca7efda7f 100755
--- a/sympy/matrices/sparse.py
+++ b/sympy/matrices/sparse.py
@@ -985,8 +985,9 @@ def col_join(self, other):
         >>> C == A.row_insert(A.rows, Matrix(B))
         True
         """
-        if not self:
-            return type(self)(other)
+        # A null matrix can always be stacked (see #10770)
+        if self.rows == 0 and self.cols != other.cols:
+            return self._new(0, other.cols, []).col_join(other)
         A, B = self, other
         if not A.cols == B.cols:
             raise ShapeError()
@@ -1191,8 +1192,9 @@ def row_join(self, other):
         >>> C == A.col_insert(A.cols, B)
         True
         """
-        if not self:
-            return type(self)(other)
+        # A null matrix can always be stacked (see #10770)
+        if self.cols == 0 and self.rows != other.rows:
+            return self._new(other.rows, 0, []).row_join(other)
         A, B = self, other
         if not A.rows == B.rows:
             raise ShapeError()
```

## X02 SKILL | sympy__sympy-13031 | test-driven-development | changed=12

```diff
diff --git a/sympy/matrices/sparse.py b/sympy/matrices/sparse.py
index e6f36cdf3..7701cbc17 100755
--- a/sympy/matrices/sparse.py
+++ b/sympy/matrices/sparse.py
@@ -985,8 +985,10 @@ def col_join(self, other):
         >>> C == A.row_insert(A.rows, Matrix(B))
         True
         """
-        if not self:
-            return type(self)(other)
+        # A null matrix can always be stacked (see  #10770)
+        if self.rows == 0 and self.cols != other.cols:
+            return self._new(0, other.cols, []).col_join(other)
+
         A, B = self, other
         if not A.cols == B.cols:
             raise ShapeError()
@@ -1191,8 +1193,10 @@ def row_join(self, other):
         >>> C == A.col_insert(A.cols, B)
         True
         """
-        if not self:
-            return type(self)(other)
+        # A null matrix can always be stacked (see  #10770)
+        if self.cols == 0 and self.rows != other.rows:
+            return self._new(other.rows, 0, []).row_join(other)
+
         A, B = self, other
         if not A.rows == B.rows:
             raise ShapeError()
```

---


## X03 BASE | sympy__sympy-18211 | test-driven-development | changed=6

```diff
diff --git a/sympy/core/relational.py b/sympy/core/relational.py
index f581bfa3c4..5a95be89da 100644
--- a/sympy/core/relational.py
+++ b/sympy/core/relational.py
@@ -388,11 +388,15 @@ def __nonzero__(self):
 
     def _eval_as_set(self):
         # self is univariate and periodicity(self, x) in (0, None)
+        from sympy.sets.conditionset import ConditionSet
         from sympy.solvers.inequalities import solve_univariate_inequality
         syms = self.free_symbols
         assert len(syms) == 1
         x = syms.pop()
-        return solve_univariate_inequality(self, x, relational=False)
+        try:
+            return solve_univariate_inequality(self, x, relational=False)
+        except NotImplementedError:
+            return ConditionSet(x, self, S.Reals)
 
     @property
     def binary_symbols(self):
```

## X03 SKILL | sympy__sympy-18211 | test-driven-development | changed=6

```diff
diff --git a/sympy/core/relational.py b/sympy/core/relational.py
index f581bfa3c4..c6aee599cf 100644
--- a/sympy/core/relational.py
+++ b/sympy/core/relational.py
@@ -389,10 +389,14 @@ def __nonzero__(self):
     def _eval_as_set(self):
         # self is univariate and periodicity(self, x) in (0, None)
         from sympy.solvers.inequalities import solve_univariate_inequality
+        from sympy.sets import ConditionSet
         syms = self.free_symbols
         assert len(syms) == 1
         x = syms.pop()
-        return solve_univariate_inequality(self, x, relational=False)
+        try:
+            return solve_univariate_inequality(self, x, relational=False)
+        except NotImplementedError:
+            return ConditionSet(x, self, S.Reals)
 
     @property
     def binary_symbols(self):
```

---


## X04 BASE | sympy__sympy-17630 | code-review-and-quality | changed=7

```diff
diff --git a/sympy/matrices/expressions/matexpr.py b/sympy/matrices/expressions/matexpr.py
index fd1e6d970a..180e488dcb 100755
--- a/sympy/matrices/expressions/matexpr.py
+++ b/sympy/matrices/expressions/matexpr.py
@@ -609,6 +609,9 @@ def _postprocessor(expr):
         if not matrices:
             return cls._from_args(nonmatrices)
 
+        if not nonmatrices:
+            return mat_class(*matrices).doit(deep=False)
+
         if nonmatrices:
             if cls == Mul:
                 for i in range(len(matrices)):
```

## X04 SKILL | sympy__sympy-17630 | code-review-and-quality | changed=7

```diff
diff --git a/sympy/matrices/expressions/matexpr.py b/sympy/matrices/expressions/matexpr.py
index fd1e6d970a..ac5c415ae1 100755
--- a/sympy/matrices/expressions/matexpr.py
+++ b/sympy/matrices/expressions/matexpr.py
@@ -627,7 +627,12 @@ def _postprocessor(expr):
                 # manipulate them like non-commutative scalars.
                 return cls._from_args(nonmatrices + [mat_class(*matrices).doit(deep=False)])
 
-        return mat_class(cls._from_args(nonmatrices), *matrices).doit(deep=False)
+        # When there are no scalars, the identity element (e.g. S.Zero
+        # for Add) must not be prepended: MatAdd would then discard all
+        # ZeroMatrix blocks and return a scalar zero instead.
+        if nonmatrices:
+            return mat_class(cls._from_args(nonmatrices), *matrices).doit(deep=False)
+        return mat_class(*matrices).doit(deep=False)
     return _postprocessor
```

---


## X05 BASE | django__django-13028 | verification-before-completion | changed=5

```diff
diff --git a/django/db/models/sql/query.py b/django/db/models/sql/query.py
index ce18098fd2..d65141b834 100755
--- a/django/db/models/sql/query.py
+++ b/django/db/models/sql/query.py
@@ -1124,7 +1124,10 @@ class Query(BaseExpression):
 
     def check_filterable(self, expression):
         """Raise an error if expression cannot be used in a WHERE clause."""
-        if not getattr(expression, 'filterable', True):
+        if (
+            hasattr(expression, 'resolve_expression') and
+            not getattr(expression, 'filterable', True)
+        ):
             raise NotSupportedError(
                 expression.__class__.__name__ + ' is disallowed in the filter '
                 'clause.'
```

## X05 SKILL | django__django-13028 | verification-before-completion | changed=5

```diff
diff --git a/django/db/models/sql/query.py b/django/db/models/sql/query.py
index ce18098fd2..c36b9ac818 100755
--- a/django/db/models/sql/query.py
+++ b/django/db/models/sql/query.py
@@ -1124,7 +1124,10 @@ class Query(BaseExpression):
 
     def check_filterable(self, expression):
         """Raise an error if expression cannot be used in a WHERE clause."""
-        if not getattr(expression, 'filterable', True):
+        if (
+            hasattr(expression, 'resolve_expression') and
+            getattr(expression, 'filterable', True) is False
+        ):
             raise NotSupportedError(
                 expression.__class__.__name__ + ' is disallowed in the filter '
                 'clause.'
```

---


## X06 BASE | pydata__xarray-6744 | python-project-structure | changed=17

```diff
diff --git a/doc/whats-new.rst b/doc/whats-new.rst
index f0b1c341..543d352d 100644
--- a/doc/whats-new.rst
+++ b/doc/whats-new.rst
@@ -42,6 +42,11 @@ Bug fixes
   allowing the ``encoding`` and ``unlimited_dims`` options with ``save_mfdataset``.
   (:issue:`6684`)
   By `Travis A. O'Brien <https://github.com/taobrienlbl>`_.
+- Fixed :py:meth:`DataArrayRolling.__iter__` ignoring the ``center`` keyword
+  argument, so that manually iterating over a centered rolling object now
+  yields centered windows consistent with the rolling reductions.
+  (:issue:`6738`)
+  By `Michael Niklas <https://github.com/headtr1ck>`_.
 - Fix backend support of pydap versions <3.3.0  (:issue:`6648`, :pull:`6656`).
   By `Hauke Schulz <https://github.com/observingClouds>`_.
 - :py:meth:`Dataset.where` with ``drop=True`` now behaves correctly with mixed dimensions.
diff --git a/xarray/core/rolling.py b/xarray/core/rolling.py
index aef290f6..14310d1d 100644
--- a/xarray/core/rolling.py
+++ b/xarray/core/rolling.py
@@ -270,13 +270,18 @@ class DataArrayRolling(Rolling["DataArray"]):
     def __iter__(self) -> Iterator[tuple[RollingKey, DataArray]]:
         if self.ndim > 1:
             raise ValueError("__iter__ is only supported for 1d-rolling")
-        stops = np.arange(1, len(self.window_labels) + 1)
-        starts = stops - int(self.window[0])
-        starts[: int(self.window[0])] = 0
-        for (label, start, stop) in zip(self.window_labels, starts, stops):
-            window = self.obj.isel({self.dim[0]: slice(start, stop)})
 
-            counts = window.count(dim=self.dim[0])
+        dim0 = self.dim[0]
+        window0 = int(self.window[0])
+        offset = (window0 + 1) // 2 if self.center[0] else 1
+        stops = np.arange(offset, self.obj.sizes[dim0] + offset)
+        starts = stops - window0
+        starts[: window0 - offset] = 0
+
+        for label, start, stop in zip(self.window_labels, starts, stops):
+            window = self.obj.isel({dim0: slice(start, stop)})
+
+            counts = window.count(dim=dim0)
             window = window.where(counts >= self.min_periods)
 
             yield (label, window)
```

## X06 SKILL | pydata__xarray-6744 | python-project-structure | changed=17

```diff
diff --git a/xarray/core/rolling.py b/xarray/core/rolling.py
index aef290f6..ef9d8028 100644
--- a/xarray/core/rolling.py
+++ b/xarray/core/rolling.py
@@ -270,13 +270,18 @@ class DataArrayRolling(Rolling["DataArray"]):
     def __iter__(self) -> Iterator[tuple[RollingKey, DataArray]]:
         if self.ndim > 1:
             raise ValueError("__iter__ is only supported for 1d-rolling")
-        stops = np.arange(1, len(self.window_labels) + 1)
-        starts = stops - int(self.window[0])
-        starts[: int(self.window[0])] = 0
-        for (label, start, stop) in zip(self.window_labels, starts, stops):
-            window = self.obj.isel({self.dim[0]: slice(start, stop)})
 
-            counts = window.count(dim=self.dim[0])
+        dim0 = self.dim[0]
+        window0 = int(self.window[0])
+        offset = (window0 + 1) // 2 if self.center[0] else 1
+        stops = np.arange(offset, self.obj.sizes[dim0] + offset)
+        starts = stops - window0
+        starts[: window0 - offset] = 0
+
+        for label, start, stop in zip(self.window_labels, starts, stops):
+            window = self.obj.isel({dim0: slice(start, stop)})
+
+            counts = window.count(dim=[dim0])
             window = window.where(counts >= self.min_periods)
 
             yield (label, window)
```

---


## X07 BASE | django__django-13346 | django-patterns | changed=20

```diff
diff --git a/django/db/models/fields/json.py b/django/db/models/fields/json.py
index fafc1beee8..8944260147 100644
--- a/django/db/models/fields/json.py
+++ b/django/db/models/fields/json.py
@@ -378,6 +378,32 @@ class KeyTransformIsNull(lookups.IsNull):
         return super().as_sql(compiler, connection)
 
 
+class KeyTransformIn(lookups.In):
+    def resolve_expression_parameter(self, compiler, connection, sql, param):
+        sql, params = super().resolve_expression_parameter(
+            compiler, connection, sql, param,
+        )
+        if (
+            not hasattr(param, 'as_sql') and
+            not connection.features.has_native_json_field
+        ):
+            if connection.vendor == 'oracle':
+                value = json.loads(param)
+                sql = "COALESCE(JSON_QUERY('%s', '$.value'), JSON_VALUE('%s', '$.value'))" % (
+                    json.dumps({'value': value}),
+                    json.dumps({'value': value}),
+                )
+                params = []
+            elif connection.vendor == 'mysql':
+                sql = "JSON_EXTRACT(%s, '$')" % sql
+            elif connection.vendor == 'sqlite':
+                if param == 'null':
+                    sql = "JSON_TYPE(%s, '$')" % sql
+                else:
+                    sql = "JSON_EXTRACT(%s, '$')" % sql
+        return sql, params
+
+
 class KeyTransformExact(JSONExact):
     def process_lhs(self, compiler, connection):
         lhs, lhs_params = super().process_lhs(compiler, connection)
@@ -482,6 +508,7 @@ class KeyTransformGte(KeyTransformNumericLookupMixin, lookups.GreaterThanOrEqual
 KeyTransform.register_lookup(KeyTransformExact)
 KeyTransform.register_lookup(KeyTransformIExact)
 KeyTransform.register_lookup(KeyTransformIsNull)
+KeyTransform.register_lookup(KeyTransformIn)
 KeyTransform.register_lookup(KeyTransformIContains)
 KeyTransform.register_lookup(KeyTransformStartsWith)
 KeyTransform.register_lookup(KeyTransformIStartsWith)
```

## X07 SKILL | django__django-13346 | django-patterns | changed=20

```diff
diff --git a/django/db/models/fields/json.py b/django/db/models/fields/json.py
index fafc1beee8..979e93266d 100644
--- a/django/db/models/fields/json.py
+++ b/django/db/models/fields/json.py
@@ -479,6 +479,25 @@ class KeyTransformGte(KeyTransformNumericLookupMixin, lookups.GreaterThanOrEqual
     pass
 
 
+class KeyTransformIn(lookups.In):
+    def resolve_expression_parameter(self, compiler, connection, sql, param):
+        sql, params = super().resolve_expression_parameter(
+            compiler, connection, sql, param,
+        )
+        if (
+            not hasattr(param, 'as_sql') and
+            not connection.features.has_native_json_field
+        ):
+            if connection.vendor == 'oracle':
+                value = json.loads(param)
+                function = 'JSON_QUERY' if isinstance(value, (list, dict)) else 'JSON_VALUE'
+                sql = "%s(%s, '$.value')" % (function, sql)
+                params = [json.dumps({'value': value})]
+            elif connection.vendor in ('mysql', 'sqlite'):
+                sql = "JSON_EXTRACT(%s, '$')" % sql
+        return sql, params
+
+
 KeyTransform.register_lookup(KeyTransformExact)
 KeyTransform.register_lookup(KeyTransformIExact)
 KeyTransform.register_lookup(KeyTransformIsNull)
@@ -494,6 +513,7 @@ KeyTransform.register_lookup(KeyTransformLt)
 KeyTransform.register_lookup(KeyTransformLte)
 KeyTransform.register_lookup(KeyTransformGt)
 KeyTransform.register_lookup(KeyTransformGte)
+KeyTransform.register_lookup(KeyTransformIn)
 
 
 class KeyTransformFactory:
```

---


## X08 BASE | sphinx-doc__sphinx-10449 | verification-before-completion | changed=20

```diff
diff --git a/sphinx/ext/autodoc/typehints.py b/sphinx/ext/autodoc/typehints.py
index 06768168e..72909d8f7 100644
--- a/sphinx/ext/autodoc/typehints.py
+++ b/sphinx/ext/autodoc/typehints.py
@@ -59,7 +59,10 @@ def merge_typehints(app: Sphinx, domain: str, objtype: str, contentnode: Element
 
         for field_list in field_lists:
             if app.config.autodoc_typehints_description_target == "all":
-                modify_field_list(field_list, annotations[fullname])
+                if objtype == "class":
+                    modify_field_list(field_list, annotations[fullname], suppress_rtype=True)
+                else:
+                    modify_field_list(field_list, annotations[fullname])
             elif app.config.autodoc_typehints_description_target == "documented_params":
                 augment_descriptions_with_types(
                     field_list, annotations[fullname], force_rtype=True
@@ -83,7 +86,8 @@ def insert_field_list(node: Element) -> nodes.field_list:
     return field_list
 
 
-def modify_field_list(node: nodes.field_list, annotations: Dict[str, str]) -> None:
+def modify_field_list(node: nodes.field_list, annotations: Dict[str, str],
+                      suppress_rtype: bool = False) -> None:
     arguments: Dict[str, Dict[str, bool]] = {}
     fields = cast(Iterable[nodes.field], node)
     for field in fields:
@@ -123,7 +127,7 @@ def modify_field_list(node: nodes.field_list, annotations: Dict[str, str]) -> No
             field += nodes.field_body('', nodes.paragraph('', ''))
             node += field
 
-    if 'return' in annotations and 'return' not in arguments:
+    if 'return' in annotations and 'return' not in arguments and not suppress_rtype:
         field = nodes.field()
         field += nodes.field_name('', 'rtype')
         field += nodes.field_body('', nodes.paragraph('', annotation))
```

## X08 SKILL | sphinx-doc__sphinx-10449 | verification-before-completion | changed=20

```diff
diff --git a/sphinx/ext/autodoc/typehints.py b/sphinx/ext/autodoc/typehints.py
index 06768168e..53d831b5e 100644
--- a/sphinx/ext/autodoc/typehints.py
+++ b/sphinx/ext/autodoc/typehints.py
@@ -57,16 +57,20 @@ def merge_typehints(app: Sphinx, domain: str, objtype: str, contentnode: Element
             field_list = insert_field_list(contentnode)
             field_lists.append(field_list)
 
+        suppress_rtype = objtype in ('class', 'exception')
         for field_list in field_lists:
             if app.config.autodoc_typehints_description_target == "all":
-                modify_field_list(field_list, annotations[fullname])
+                modify_field_list(field_list, annotations[fullname],
+                                  suppress_rtype=suppress_rtype)
             elif app.config.autodoc_typehints_description_target == "documented_params":
                 augment_descriptions_with_types(
-                    field_list, annotations[fullname], force_rtype=True
+                    field_list, annotations[fullname], force_rtype=True,
+                    suppress_rtype=suppress_rtype
                 )
             else:
                 augment_descriptions_with_types(
-                    field_list, annotations[fullname], force_rtype=False
+                    field_list, annotations[fullname], force_rtype=False,
+                    suppress_rtype=suppress_rtype
                 )
 
 
@@ -83,7 +87,8 @@ def insert_field_list(node: Element) -> nodes.field_list:
     return field_list
 
 
-def modify_field_list(node: nodes.field_list, annotations: Dict[str, str]) -> None:
+def modify_field_list(node: nodes.field_list, annotations: Dict[str, str],
+                      suppress_rtype: bool = False) -> None:
     arguments: Dict[str, Dict[str, bool]] = {}
     fields = cast(Iterable[nodes.field], node)
     for field in fields:
@@ -123,7 +128,7 @@ def modify_field_list(node: nodes.field_list, annotations: Dict[str, str]) -> No
             field += nodes.field_body('', nodes.paragraph('', ''))
             node += field
 
-    if 'return' in annotations and 'return' not in arguments:
+    if 'return' in annotations and 'return' not in arguments and not suppress_rtype:
         field = nodes.field()
         field += nodes.field_name('', 'rtype')
         field += nodes.field_body('', nodes.paragraph('', annotation))
@@ -133,7 +138,8 @@ def modify_field_list(node: nodes.field_list, annotations: Dict[str, str]) -> No
 def augment_descriptions_with_types(
     node: nodes.field_list,
     annotations: Dict[str, str],
-    force_rtype: bool
+    force_rtype: bool,
+    suppress_rtype: bool = False
 ) -> None:
     fields = cast(Iterable[nodes.field], node)
     has_description = set()  # type: Set[str]
@@ -169,7 +175,7 @@ def augment_descriptions_with_types(
             node += field
 
     # Add 'rtype' if 'return' is present and 'rtype' isn't.
-    if 'return' in annotations:
+    if 'return' in annotations and not suppress_rtype:
         rtype = annotations['return']
         if 'return' not in has_type and ('return' in has_description or
                                          (force_rtype and rtype != "None")):
```

---


## X09 BASE | django__django-15278 | django-verification | changed=14

```diff
diff --git a/django/db/backends/sqlite3/schema.py b/django/db/backends/sqlite3/schema.py
index 6752a8e3c0..3ff0a3f7db 100644
--- a/django/db/backends/sqlite3/schema.py
+++ b/django/db/backends/sqlite3/schema.py
@@ -324,10 +324,15 @@ class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
 
     def add_field(self, model, field):
         """Create a field on a model."""
-        # Fields with default values cannot by handled by ALTER TABLE ADD
-        # COLUMN statement because DROP DEFAULT is not supported in
-        # ALTER TABLE.
-        if not field.null or self.effective_default(field) is not None:
+        if (
+            # Primary keys and unique fields are not supported in ALTER TABLE
+            # ADD COLUMN.
+            field.primary_key or field.unique or
+            # Fields with default values cannot by handled by ALTER TABLE ADD
+            # COLUMN statement because DROP DEFAULT is not supported in
+            # ALTER TABLE.
+            not field.null or self.effective_default(field) is not None
+        ):
             self._remake_table(model, create_field=field)
         else:
             super().add_field(model, field)
```

## X09 SKILL | django__django-15278 | django-verification | changed=14

```diff
diff --git a/django/db/backends/sqlite3/schema.py b/django/db/backends/sqlite3/schema.py
index 6752a8e3c0..82533c53ad 100644
--- a/django/db/backends/sqlite3/schema.py
+++ b/django/db/backends/sqlite3/schema.py
@@ -324,10 +324,16 @@ class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
 
     def add_field(self, model, field):
         """Create a field on a model."""
-        # Fields with default values cannot by handled by ALTER TABLE ADD
-        # COLUMN statement because DROP DEFAULT is not supported in
-        # ALTER TABLE.
-        if not field.null or self.effective_default(field) is not None:
+        if (
+            # Primary keys and unique fields are not supported in ALTER TABLE
+            # ADD COLUMN.
+            field.primary_key or field.unique or
+            # Fields with default values cannot by handled by ALTER TABLE ADD
+            # COLUMN statement because DROP DEFAULT is not supported in
+            # ALTER TABLE.
+            not field.null or
+            self.effective_default(field) is not None
+        ):
             self._remake_table(model, create_field=field)
         else:
             super().add_field(model, field)
```

---


## X10 BASE | pytest-dev__pytest-7236 | python-testing | changed=13

```diff
diff --git a/src/_pytest/unittest.py b/src/_pytest/unittest.py
index 773f545af..1c385f1d2 100644
--- a/src/_pytest/unittest.py
+++ b/src/_pytest/unittest.py
@@ -115,6 +115,7 @@ class TestCaseFunction(Function):
     def setup(self):
         # a bound method to be called during teardown() if set (see 'runtest()')
         self._explicit_tearDown = None
+        self._needs_explicit_tearDown = False
         self._testcase = self.parent.obj(self.name)
         self._obj = getattr(self._testcase, self.name)
         if hasattr(self, "_request"):
@@ -122,7 +123,8 @@ class TestCaseFunction(Function):
 
     def teardown(self):
         if self._explicit_tearDown is not None:
-            self._explicit_tearDown()
+            if self._needs_explicit_tearDown:
+                self._explicit_tearDown()
             self._explicit_tearDown = None
         self._testcase = None
         self._obj = None
@@ -222,7 +224,11 @@ class TestCaseFunction(Function):
             # when absolutely needed
             if self.config.getoption("usepdb"):
                 self._explicit_tearDown = self._testcase.tearDown
-                setattr(self._testcase, "tearDown", lambda *args: None)
+
+                def tearDown(*args):
+                    self._needs_explicit_tearDown = True
+
+                setattr(self._testcase, "tearDown", tearDown)
 
             # we need to update the actual bound method with self.obj, because
             # wrap_pytest_function_for_tracing replaces self.obj by a wrapper
```

## X10 SKILL | pytest-dev__pytest-7236 | python-testing | changed=13

```diff
diff --git a/src/_pytest/unittest.py b/src/_pytest/unittest.py
index 773f545af..9f6242a26 100644
--- a/src/_pytest/unittest.py
+++ b/src/_pytest/unittest.py
@@ -221,8 +221,17 @@ class TestCaseFunction(Function):
             # TestCase instance interacts with the results object, so better to only do it
             # when absolutely needed
             if self.config.getoption("usepdb"):
-                self._explicit_tearDown = self._testcase.tearDown
-                setattr(self._testcase, "tearDown", lambda *args: None)
+                # Delay tearDown() until pytest's teardown phase (after the pdb
+                # prompt). The stub below is only invoked by unittest when it would
+                # normally call tearDown(); if it is not invoked (for example, when
+                # the test is skipped), then self._explicit_tearDown stays None and
+                # tearDown() is not called later either.
+                explicit_tearDown = self._testcase.tearDown
+
+                def delayed_tearDown(*args):
+                    self._explicit_tearDown = explicit_tearDown
+
+                setattr(self._testcase, "tearDown", delayed_tearDown)
 
             # we need to update the actual bound method with self.obj, because
             # wrap_pytest_function_for_tracing replaces self.obj by a wrapper
```

---


## X11 BASE | django__django-11551 | django-patterns | changed=39

```diff
diff --git a/django/contrib/admin/checks.py b/django/contrib/admin/checks.py
index f82c20c2f1..ccebbbb900 100644
--- a/django/contrib/admin/checks.py
+++ b/django/contrib/admin/checks.py
@@ -720,33 +720,32 @@ class ModelAdminChecks(BaseModelAdminChecks):
             return []
         elif hasattr(obj, item):
             return []
-        elif hasattr(obj.model, item):
+        try:
+            field = obj.model._meta.get_field(item)
+        except FieldDoesNotExist:
             try:
-                field = obj.model._meta.get_field(item)
-            except FieldDoesNotExist:
-                return []
-            else:
-                if isinstance(field, models.ManyToManyField):
-                    return [
-                        checks.Error(
-                            "The value of '%s' must not be a ManyToManyField." % label,
-                            obj=obj.__class__,
-                            id='admin.E109',
-                        )
-                    ]
-                return []
-        else:
+                field = getattr(obj.model, item)
+            except AttributeError:
+                return [
+                    checks.Error(
+                        "The value of '%s' refers to '%s', which is not a callable, "
+                        "an attribute of '%s', or an attribute or method on '%s.%s'." % (
+                            label, item, obj.__class__.__name__,
+                            obj.model._meta.app_label, obj.model._meta.object_name,
+                        ),
+                        obj=obj.__class__,
+                        id='admin.E108',
+                    )
+                ]
+        if isinstance(field, models.ManyToManyField):
             return [
                 checks.Error(
-                    "The value of '%s' refers to '%s', which is not a callable, "
-                    "an attribute of '%s', or an attribute or method on '%s.%s'." % (
-                        label, item, obj.__class__.__name__,
-                        obj.model._meta.app_label, obj.model._meta.object_name,
-                    ),
+                    "The value of '%s' must not be a ManyToManyField." % label,
                     obj=obj.__class__,
-                    id='admin.E108',
+                    id='admin.E109',
                 )
             ]
+        return []
 
     def _check_list_display_links(self, obj):
         """ Check that list_display_links is a unique subset of list_display.
```

## X11 SKILL | django__django-11551 | django-patterns | changed=39

```diff
diff --git a/django/contrib/admin/checks.py b/django/contrib/admin/checks.py
index f82c20c2f1..5be6925bd0 100644
--- a/django/contrib/admin/checks.py
+++ b/django/contrib/admin/checks.py
@@ -720,33 +720,34 @@ class ModelAdminChecks(BaseModelAdminChecks):
             return []
         elif hasattr(obj, item):
             return []
-        elif hasattr(obj.model, item):
+        else:
             try:
                 field = obj.model._meta.get_field(item)
             except FieldDoesNotExist:
-                return []
-            else:
-                if isinstance(field, models.ManyToManyField):
+                try:
+                    field = getattr(obj.model, item)
+                except AttributeError:
                     return [
                         checks.Error(
-                            "The value of '%s' must not be a ManyToManyField." % label,
+                            "The value of '%s' refers to '%s', which is not a "
+                            "callable, an attribute of '%s', or an attribute or "
+                            "method on '%s.%s'." % (
+                                label, item, obj.__class__.__name__,
+                                obj.model._meta.app_label, obj.model._meta.object_name,
+                            ),
                             obj=obj.__class__,
-                            id='admin.E109',
+                            id='admin.E108',
                         )
                     ]
-                return []
-        else:
-            return [
-                checks.Error(
-                    "The value of '%s' refers to '%s', which is not a callable, "
-                    "an attribute of '%s', or an attribute or method on '%s.%s'." % (
-                        label, item, obj.__class__.__name__,
-                        obj.model._meta.app_label, obj.model._meta.object_name,
-                    ),
-                    obj=obj.__class__,
-                    id='admin.E108',
-                )
-            ]
+            if isinstance(field, models.ManyToManyField):
+                return [
+                    checks.Error(
+                        "The value of '%s' must not be a ManyToManyField." % label,
+                        obj=obj.__class__,
+                        id='admin.E109',
+                    )
+                ]
+            return []
 
     def _check_list_display_links(self, obj):
         """ Check that list_display_links is a unique subset of list_display.
```

---


## X12 BASE | matplotlib__matplotlib-25311 | python-anti-patterns | changed=31

```diff
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
index 1dee8a23d9..cc706d9786 100755
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,7 +1505,6 @@ class DraggableBase:
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
         self.cids = [
             self.canvas.callbacks._connect_picklable(
@@ -1514,6 +1513,8 @@ class DraggableBase:
                 'button_release_event', self.on_release),
         ]
 
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x
```

## X12 SKILL | matplotlib__matplotlib-25311 | python-anti-patterns | changed=31

```diff
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
index 1dee8a23d9..5ab15b1f28 100755
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,15 +1505,21 @@ class DraggableBase:
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
-        self.cids = [
-            self.canvas.callbacks._connect_picklable(
-                'pick_event', self.on_pick),
-            self.canvas.callbacks._connect_picklable(
-                'button_release_event', self.on_release),
+        callbacks = ref_artist.figure._canvas_callbacks
+        self._disconnectors = [
+            functools.partial(
+                callbacks.disconnect, callbacks._connect_picklable(name, func))
+            for name, func in [
+                ("pick_event", self.on_pick),
+                ("button_release_event", self.on_release),
+                ("motion_notify_event", self.on_motion),
+            ]
         ]
 
+    # A property, not an attribute, to maintain picklability.
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x
@@ -1540,15 +1546,12 @@ class DraggableBase:
                 self.ref_artist.draw(
                     self.ref_artist.figure._get_renderer())
                 self.canvas.blit()
-            self._c1 = self.canvas.callbacks._connect_picklable(
-                "motion_notify_event", self.on_motion)
             self.save_offset()
 
     def on_release(self, event):
         if self._check_still_parented() and self.got_artist:
             self.finalize_offset()
             self.got_artist = False
-            self.canvas.mpl_disconnect(self._c1)
 
             if self._use_blit:
                 self.ref_artist.set_animated(False)
@@ -1562,14 +1565,8 @@ class DraggableBase:
 
     def disconnect(self):
         """Disconnect the callbacks."""
-        for cid in self.cids:
-            self.canvas.mpl_disconnect(cid)
-        try:
-            c1 = self._c1
-        except AttributeError:
-            pass
-        else:
-            self.canvas.mpl_disconnect(c1)
+        for disconnector in self._disconnectors:
+            disconnector()
 
     def save_offset(self):
         pass
```

---


## X13 BASE | django__django-10973 | django-tdd | changed=37

```diff
diff --git a/django/db/backends/postgresql/client.py b/django/db/backends/postgresql/client.py
index 7fca6eff30..99e426179d 100644
--- a/django/db/backends/postgresql/client.py
+++ b/django/db/backends/postgresql/client.py
@@ -2,17 +2,9 @@ import os
 import signal
 import subprocess
 
-from django.core.files.temp import NamedTemporaryFile
 from django.db.backends.base.client import BaseDatabaseClient
 
 
-def _escape_pgpass(txt):
-    """
-    Escape a fragment of a PostgreSQL .pgpass file.
-    """
-    return txt.replace('\\', '\\\\').replace(':', '\\:')
-
-
 class DatabaseClient(BaseDatabaseClient):
     executable_name = 'psql'
 
@@ -34,38 +26,18 @@ class DatabaseClient(BaseDatabaseClient):
             args += ['-p', str(port)]
         args += [dbname]
 
-        temp_pgpass = None
+        env = os.environ.copy()
+        if passwd:
+            env['PGPASSWORD'] = passwd
+
         sigint_handler = signal.getsignal(signal.SIGINT)
         try:
-            if passwd:
-                # Create temporary .pgpass file.
-                temp_pgpass = NamedTemporaryFile(mode='w+')
-                try:
-                    print(
-                        _escape_pgpass(host) or '*',
-                        str(port) or '*',
-                        _escape_pgpass(dbname) or '*',
-                        _escape_pgpass(user) or '*',
-                        _escape_pgpass(passwd),
-                        file=temp_pgpass,
-                        sep=':',
-                        flush=True,
-                    )
-                    os.environ['PGPASSFILE'] = temp_pgpass.name
-                except UnicodeEncodeError:
-                    # If the current locale can't encode the data, let the
-                    # user input the password manually.
-                    pass
             # Allow SIGINT to pass to psql to abort queries.
             signal.signal(signal.SIGINT, signal.SIG_IGN)
-            subprocess.check_call(args)
+            subprocess.run(args, check=True, env=env)
         finally:
             # Restore the original SIGINT handler.
             signal.signal(signal.SIGINT, sigint_handler)
-            if temp_pgpass:
-                temp_pgpass.close()
-                if 'PGPASSFILE' in os.environ:  # unit tests need cleanup
-                    del os.environ['PGPASSFILE']
 
     def runshell(self):
         DatabaseClient.runshell_db(self.connection.get_connection_params())
```

## X13 SKILL | django__django-10973 | django-tdd | changed=37

```diff
diff --git a/django/db/backends/postgresql/client.py b/django/db/backends/postgresql/client.py
index 7fca6eff30..cf4df76882 100644
--- a/django/db/backends/postgresql/client.py
+++ b/django/db/backends/postgresql/client.py
@@ -2,17 +2,9 @@ import os
 import signal
 import subprocess
 
-from django.core.files.temp import NamedTemporaryFile
 from django.db.backends.base.client import BaseDatabaseClient
 
 
-def _escape_pgpass(txt):
-    """
-    Escape a fragment of a PostgreSQL .pgpass file.
-    """
-    return txt.replace('\\', '\\\\').replace(':', '\\:')
-
-
 class DatabaseClient(BaseDatabaseClient):
     executable_name = 'psql'
 
@@ -34,38 +26,17 @@ class DatabaseClient(BaseDatabaseClient):
             args += ['-p', str(port)]
         args += [dbname]
 
-        temp_pgpass = None
         sigint_handler = signal.getsignal(signal.SIGINT)
+        subprocess_env = os.environ.copy()
+        if passwd:
+            subprocess_env['PGPASSWORD'] = str(passwd)
         try:
-            if passwd:
-                # Create temporary .pgpass file.
-                temp_pgpass = NamedTemporaryFile(mode='w+')
-                try:
-                    print(
-                        _escape_pgpass(host) or '*',
-                        str(port) or '*',
-                        _escape_pgpass(dbname) or '*',
-                        _escape_pgpass(user) or '*',
-                        _escape_pgpass(passwd),
-                        file=temp_pgpass,
-                        sep=':',
-                        flush=True,
-                    )
-                    os.environ['PGPASSFILE'] = temp_pgpass.name
-                except UnicodeEncodeError:
-                    # If the current locale can't encode the data, let the
-                    # user input the password manually.
-                    pass
             # Allow SIGINT to pass to psql to abort queries.
             signal.signal(signal.SIGINT, signal.SIG_IGN)
-            subprocess.check_call(args)
+            subprocess.run(args, check=True, env=subprocess_env)
         finally:
             # Restore the original SIGINT handler.
             signal.signal(signal.SIGINT, sigint_handler)
-            if temp_pgpass:
-                temp_pgpass.close()
-                if 'PGPASSFILE' in os.environ:  # unit tests need cleanup
-                    del os.environ['PGPASSFILE']
 
     def runshell(self):
         DatabaseClient.runshell_db(self.connection.get_connection_params())
```

---


## X14 BASE | sympy__sympy-24443 | python-project-structure | changed=44

```diff
diff --git a/sympy/combinatorics/homomorphisms.py b/sympy/combinatorics/homomorphisms.py
index bb7bdf32ba..fd3260da97 100644
--- a/sympy/combinatorics/homomorphisms.py
+++ b/sympy/combinatorics/homomorphisms.py
@@ -308,42 +308,26 @@ def homomorphism(domain, codomain, gens, images=(), check=True):
     return GroupHomomorphism(domain, codomain, images)
 
 def _check_homomorphism(domain, codomain, images):
-    if hasattr(domain, 'relators'):
-        rels = domain.relators
+    if isinstance(domain, PermutationGroup):
+        presentation = domain.presentation()
+        gens = presentation.generators
+        rels = presentation.relators
+        images = dict(zip(gens, (images[g] for g in domain.generators)))
     else:
-        gens = domain.presentation().generators
-        rels = domain.presentation().relators
+        rels = domain.relators
+
     identity = codomain.identity
 
     def _image(r):
         if r.is_identity:
             return identity
-        else:
-            w = identity
-            r_arr = r.array_form
-            i = 0
-            j = 0
-            # i is the index for r and j is for
-            # r_arr. r_arr[j] is the tuple (sym, p)
-            # where sym is the generator symbol
-            # and p is the power to which it is
-            # raised while r[i] is a generator
-            # (not just its symbol) or the inverse of
-            # a generator - hence the need for
-            # both indices
-            while i < len(r):
-                power = r_arr[j][1]
-                if isinstance(domain, PermutationGroup) and r[i] in gens:
-                    s = domain.generators[gens.index(r[i])]
-                else:
-                    s = r[i]
-                if s in images:
-                    w = w*images[s]**power
-                elif s**-1 in images:
-                    w = w*images[s**-1]**power
-                i += abs(power)
-                j += 1
-            return w
+        w = identity
+        for s in r.letter_form_elm:
+            if s in images:
+                w = w*images[s]
+            else:
+                w = w*images[s**-1]**-1
+        return w
 
     for r in rels:
         if isinstance(codomain, FpGroup):
```

## X14 SKILL | sympy__sympy-24443 | python-project-structure | changed=44

```diff
diff --git a/sympy/combinatorics/homomorphisms.py b/sympy/combinatorics/homomorphisms.py
index bb7bdf32ba..905268efcf 100644
--- a/sympy/combinatorics/homomorphisms.py
+++ b/sympy/combinatorics/homomorphisms.py
@@ -310,40 +310,24 @@ def homomorphism(domain, codomain, gens, images=(), check=True):
 def _check_homomorphism(domain, codomain, images):
     if hasattr(domain, 'relators'):
         rels = domain.relators
+        # for an FpGroup (or FreeGroup) the relators are written
+        # directly in terms of ``domain.generators``
+        gen_of_symbol = {gen.array_form[0][0]: gen for gen in domain.generators}
     else:
-        gens = domain.presentation().generators
-        rels = domain.presentation().relators
+        pres = domain.presentation()
+        rels = pres.relators
+        # the relators are written in terms of the presentation
+        # generators, which correspond to ``domain.generators``
+        # positionally
+        gen_of_symbol = {sym.array_form[0][0]: gen
+                         for sym, gen in zip(pres.generators, domain.generators)}
     identity = codomain.identity
 
     def _image(r):
-        if r.is_identity:
-            return identity
-        else:
-            w = identity
-            r_arr = r.array_form
-            i = 0
-            j = 0
-            # i is the index for r and j is for
-            # r_arr. r_arr[j] is the tuple (sym, p)
-            # where sym is the generator symbol
-            # and p is the power to which it is
-            # raised while r[i] is a generator
-            # (not just its symbol) or the inverse of
-            # a generator - hence the need for
-            # both indices
-            while i < len(r):
-                power = r_arr[j][1]
-                if isinstance(domain, PermutationGroup) and r[i] in gens:
-                    s = domain.generators[gens.index(r[i])]
-                else:
-                    s = r[i]
-                if s in images:
-                    w = w*images[s]**power
-                elif s**-1 in images:
-                    w = w*images[s**-1]**power
-                i += abs(power)
-                j += 1
-            return w
+        w = identity
+        for sym, power in r.array_form:
+            w = w*images[gen_of_symbol[sym]]**power
+        return w
 
     for r in rels:
         if isinstance(codomain, FpGroup):
```

---


## X15 BASE | django__django-13837 | django-tdd | changed=34

```diff
diff --git a/django/utils/autoreload.py b/django/utils/autoreload.py
index b8efb9f881..61573b15b4 100644
--- a/django/utils/autoreload.py
+++ b/django/utils/autoreload.py
@@ -216,33 +216,46 @@ def get_child_arguments():
     executable is reported to not have the .exe extension which can cause bugs
     on reloading.
     """
-    import django.__main__
-    django_main_path = Path(django.__main__.__file__)
+    import __main__
     py_script = Path(sys.argv[0])
 
     args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions]
-    if py_script == django_main_path:
-        # The server was started with `python -m django runserver`.
-        args += ['-m', 'django']
+    # __spec__ is set when Python was started with the `-m` option and when a
+    # directory or zip file is passed on the command line. In the former case
+    # the spec's parent is the package name passed to `-m`; in the latter it is
+    # the empty string.
+    # See https://docs.python.org/3/reference/import.html#main-spec
+    main_spec = getattr(__main__, '__spec__', None)
+    if main_spec is not None and main_spec.parent:
+        # The server was started with `python -m pkg runserver`.
+        args += ['-m', main_spec.parent]
         args += sys.argv[1:]
-    elif not py_script.exists():
-        # sys.argv[0] may not exist for several reasons on Windows.
-        # It may exist with a .exe extension or have a -script.py suffix.
-        exe_entrypoint = py_script.with_suffix('.exe')
-        if exe_entrypoint.exists():
-            # Should be executed directly, ignoring sys.executable.
-            # TODO: Remove str() when dropping support for PY37.
-            # args parameter accepts path-like on Windows from Python 3.8.
-            return [str(exe_entrypoint), *sys.argv[1:]]
-        script_entrypoint = py_script.with_name('%s-script.py' % py_script.name)
-        if script_entrypoint.exists():
-            # Should be executed as usual.
-            # TODO: Remove str() when dropping support for PY37.
-            # args parameter accepts path-like on Windows from Python 3.8.
-            return [*args, str(script_entrypoint), *sys.argv[1:]]
-        raise RuntimeError('Script %s does not exist.' % py_script)
     else:
-        args += sys.argv
+        # Fall back to detecting `python -m django` when __main__.__spec__ is
+        # unavailable.
+        import django.__main__
+        if py_script == Path(django.__main__.__file__):
+            # The server was started with `python -m django runserver`.
+            args += ['-m', 'django']
+            args += sys.argv[1:]
+        elif not py_script.exists():
+            # sys.argv[0] may not exist for several reasons on Windows.
+            # It may exist with a .exe extension or have a -script.py suffix.
+            exe_entrypoint = py_script.with_suffix('.exe')
+            if exe_entrypoint.exists():
+                # Should be executed directly, ignoring sys.executable.
+                # TODO: Remove str() when dropping support for PY37.
+                # args parameter accepts path-like on Windows from Python 3.8.
+                return [str(exe_entrypoint), *sys.argv[1:]]
+            script_entrypoint = py_script.with_name('%s-script.py' % py_script.name)
+            if script_entrypoint.exists():
+                # Should be executed as usual.
+                # TODO: Remove str() when dropping support for PY37.
+                # args parameter accepts path-like on Windows from Python 3.8.
+                return [*args, str(script_entrypoint), *sys.argv[1:]]
+            raise RuntimeError('Script %s does not exist.' % py_script)
+        else:
+            args += sys.argv
     return args
```

## X15 SKILL | django__django-13837 | django-tdd | changed=34

```diff
diff --git a/django/utils/autoreload.py b/django/utils/autoreload.py
index b8efb9f881..b7b320cb34 100644
--- a/django/utils/autoreload.py
+++ b/django/utils/autoreload.py
@@ -216,16 +216,33 @@ def get_child_arguments():
     executable is reported to not have the .exe extension which can cause bugs
     on reloading.
     """
-    import django.__main__
-    django_main_path = Path(django.__main__.__file__)
+    import __main__
     py_script = Path(sys.argv[0])
 
     args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions]
-    if py_script == django_main_path:
-        # The server was started with `python -m django runserver`.
-        args += ['-m', 'django']
-        args += sys.argv[1:]
-    elif not py_script.exists():
+    # __spec__ is set when the server was started with the `-m` option,
+    # see https://docs.python.org/3/reference/import.html#main-spec
+    # __spec__ may not exist, e.g. when running in a Conda env.
+    if getattr(__main__, '__spec__', None) is not None:
+        spec = __main__.__spec__
+        # __spec__.parent is the package name when Python was started with
+        # `python -m package` and the empty string for a directory or zip file.
+        parent = getattr(spec, 'parent', None)
+        if isinstance(parent, str) and parent:
+            module = parent
+        else:
+            # A top-level module started with `python -m module` has an empty
+            # parent, but its name is available in __spec__.name.
+            name = getattr(spec, 'name', None)
+            if isinstance(name, str) and name != '__main__':
+                module = name
+            else:
+                module = None
+        if module:
+            args += ['-m', module]
+            args += sys.argv[1:]
+            return args
+    if not py_script.exists():
         # sys.argv[0] may not exist for several reasons on Windows.
         # It may exist with a .exe extension or have a -script.py suffix.
         exe_entrypoint = py_script.with_suffix('.exe')
@@ -241,8 +258,7 @@ def get_child_arguments():
             # args parameter accepts path-like on Windows from Python 3.8.
             return [*args, str(script_entrypoint), *sys.argv[1:]]
         raise RuntimeError('Script %s does not exist.' % py_script)
-    else:
-        args += sys.argv
+    args += sys.argv
     return args
```

---
