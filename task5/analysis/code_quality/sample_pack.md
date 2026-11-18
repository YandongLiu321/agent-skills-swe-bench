# Patch pairs for close reading (baseline vs skill, same instance, resolved)


## P01 BASE | matplotlib__matplotlib-22871 | test-driven-development | changed=5

```diff
diff --git a/lib/matplotlib/dates.py b/lib/matplotlib/dates.py
index 4d8ddf3ee5..f4bd277169 100644
--- a/lib/matplotlib/dates.py
+++ b/lib/matplotlib/dates.py
@@ -799,6 +799,11 @@ class ConciseDateFormatter(ticker.Formatter):
             if len(np.unique(tickdate[:, level])) > 1:
                 if level < 2:
                     show_offset = False
+                    if level == 1 and not np.any(tickdate[:, 1] == 1):
+                        # A January tick would be labelled with the year
+                        # (via zero_formats[1] == '%Y'); if there is no
+                        # January tick, the year must be shown in the offset.
+                        show_offset = self.show_offset
                 break
             elif level == 0:
                 # all tickdate are the same, so only micros might be different
```

## P01 SKILL | matplotlib__matplotlib-22871 | test-driven-development | changed=5

```diff
diff --git a/lib/matplotlib/dates.py b/lib/matplotlib/dates.py
index 4d8ddf3ee5..93b5f5f7db 100644
--- a/lib/matplotlib/dates.py
+++ b/lib/matplotlib/dates.py
@@ -797,7 +797,10 @@ class ConciseDateFormatter(ticker.Formatter):
         # 3: hours, 4: minutes, 5: seconds, 6: microseconds
         for level in range(5, -1, -1):
             if len(np.unique(tickdate[:, level])) > 1:
-                if level < 2:
+                # If the level is less than 2, the year may already be present
+                # in the axis: either the ticks are years, or January is
+                # included and its label contains the year.
+                if level < 2 and (tickdate[:, 1] == 1).any():
                     show_offset = False
                 break
             elif level == 0:
```

---


## P02 BASE | astropy__astropy-14508 | verification-before-completion | changed=5

```diff
diff --git a/astropy/io/fits/card.py b/astropy/io/fits/card.py
index 118bfced8..1bf73a2b6 100644
--- a/astropy/io/fits/card.py
+++ b/astropy/io/fits/card.py
@@ -1299,7 +1299,15 @@ def _format_value(value):
 
 def _format_float(value):
     """Format a floating number to make sure it gets the decimal point."""
-    value_str = f"{value:.16G}"
+    # Use the shorter of Python's shortest round-tripping representation and
+    # the fixed-precision representation.  This avoids unnecessarily long
+    # cards for values such as 0.009125, which the fixed-precision format
+    # would expand to 0.009124999999999999.
+    value_str = min(f"{value:.16G}", str(value), key=len)
+
+    # Python uses a lowercase "e" for exponents, but FITS uses uppercase "E".
+    value_str = value_str.replace("e", "E")
+
     if "." not in value_str and "E" not in value_str:
         value_str += ".0"
     elif "E" in value_str:
```

## P02 SKILL | astropy__astropy-14508 | verification-before-completion | changed=5

```diff
diff --git a/astropy/io/fits/card.py b/astropy/io/fits/card.py
index 118bfced8..4fb92bea9 100644
--- a/astropy/io/fits/card.py
+++ b/astropy/io/fits/card.py
@@ -1299,7 +1299,10 @@ def _format_value(value):
 
 def _format_float(value):
     """Format a floating number to make sure it gets the decimal point."""
-    value_str = f"{value:.16G}"
+    value_str = str(value).upper()
+    if len(value_str) > 20:
+        value_str = f"{value:.16G}"
+
     if "." not in value_str and "E" not in value_str:
         value_str += ".0"
     elif "E" in value_str:
```

---


## P03 BASE | astropy__astropy-14309 | python-anti-patterns | changed=5

```diff
diff --git a/astropy/io/fits/connect.py b/astropy/io/fits/connect.py
index 4b6150f4a..2be2d1210 100644
--- a/astropy/io/fits/connect.py
+++ b/astropy/io/fits/connect.py
@@ -65,11 +65,12 @@ def is_fits(origin, filepath, fileobj, *args, **kwargs):
         fileobj.seek(pos)
         return sig == FITS_SIGNATURE
     elif filepath is not None:
-        if filepath.lower().endswith(
+        return filepath.lower().endswith(
             (".fits", ".fits.gz", ".fit", ".fit.gz", ".fts", ".fts.gz")
-        ):
-            return True
-    return isinstance(args[0], (HDUList, TableHDU, BinTableHDU, GroupsHDU))
+        )
+    return len(args) > 0 and isinstance(
+        args[0], (HDUList, TableHDU, BinTableHDU, GroupsHDU)
+    )
 
 
 def _decode_mixins(tbl):
```

## P03 SKILL | astropy__astropy-14309 | python-anti-patterns | changed=5

```diff
diff --git a/astropy/io/fits/connect.py b/astropy/io/fits/connect.py
index 4b6150f4a..210af2b96 100644
--- a/astropy/io/fits/connect.py
+++ b/astropy/io/fits/connect.py
@@ -65,10 +65,9 @@ def is_fits(origin, filepath, fileobj, *args, **kwargs):
         fileobj.seek(pos)
         return sig == FITS_SIGNATURE
     elif filepath is not None:
-        if filepath.lower().endswith(
+        return filepath.lower().endswith(
             (".fits", ".fits.gz", ".fit", ".fit.gz", ".fts", ".fts.gz")
-        ):
-            return True
+        )
     return isinstance(args[0], (HDUList, TableHDU, BinTableHDU, GroupsHDU))
```

---


## P04 BASE | astropy__astropy-7606 | code-review-and-quality | changed=5

```diff
diff --git a/astropy/units/core.py b/astropy/units/core.py
index e9bd986d3..5d35c5b12 100644
--- a/astropy/units/core.py
+++ b/astropy/units/core.py
@@ -1710,7 +1710,14 @@ class UnrecognizedUnit(IrreducibleUnit):
         _unrecognized_operator
 
     def __eq__(self, other):
-        other = Unit(other, parse_strict='silent')
+        if self is other:
+            return True
+
+        try:
+            other = Unit(other, parse_strict='silent')
+        except (ValueError, UnitsError, TypeError):
+            return False
+
         return isinstance(other, UnrecognizedUnit) and self.name == other.name
 
     def __ne__(self, other):
```

## P04 SKILL | astropy__astropy-7606 | code-review-and-quality | changed=5

```diff
diff --git a/astropy/units/core.py b/astropy/units/core.py
index e9bd986d3..0ee8cf869 100644
--- a/astropy/units/core.py
+++ b/astropy/units/core.py
@@ -1710,7 +1710,10 @@ class UnrecognizedUnit(IrreducibleUnit):
         _unrecognized_operator
 
     def __eq__(self, other):
-        other = Unit(other, parse_strict='silent')
+        try:
+            other = Unit(other, parse_strict='silent')
+        except (ValueError, UnitsError, TypeError):
+            return False
         return isinstance(other, UnrecognizedUnit) and self.name == other.name
 
     def __ne__(self, other):
```

---


## P05 BASE | django__django-16899 | django-patterns | changed=5

```diff
diff --git a/django/contrib/admin/checks.py b/django/contrib/admin/checks.py
index c395b0bde2..2034aa8d4e 100644
--- a/django/contrib/admin/checks.py
+++ b/django/contrib/admin/checks.py
@@ -771,10 +771,12 @@ class BaseModelAdminChecks:
             except FieldDoesNotExist:
                 return [
                     checks.Error(
-                        "The value of '%s' is not a callable, an attribute of "
-                        "'%s', or an attribute of '%s'."
+                        "The value of '%s' refers to '%s', which is not a "
+                        "callable, an attribute of '%s', or an attribute of "
+                        "'%s'."
                         % (
                             label,
+                            field_name,
                             obj.__class__.__name__,
                             obj.model._meta.label,
                         ),
```

## P05 SKILL | django__django-16899 | django-patterns | changed=5

```diff
diff --git a/django/contrib/admin/checks.py b/django/contrib/admin/checks.py
index c395b0bde2..373131e1ff 100644
--- a/django/contrib/admin/checks.py
+++ b/django/contrib/admin/checks.py
@@ -771,10 +771,11 @@ class BaseModelAdminChecks:
             except FieldDoesNotExist:
                 return [
                     checks.Error(
-                        "The value of '%s' is not a callable, an attribute of "
-                        "'%s', or an attribute of '%s'."
+                        "The value of '%s' refers to '%s', which is not a "
+                        "callable, an attribute of '%s', or an attribute of '%s'."
                         % (
                             label,
+                            field_name,
                             obj.__class__.__name__,
                             obj.model._meta.label,
                         ),
```

---


## P06 BASE | sympy__sympy-12481 | verification-before-completion | changed=13

```diff
diff --git a/sympy/combinatorics/permutations.py b/sympy/combinatorics/permutations.py
index 136ed5a47..4ac1c2ef3 100755
--- a/sympy/combinatorics/permutations.py
+++ b/sympy/combinatorics/permutations.py
@@ -895,12 +895,8 @@ def __new__(cls, *args, **kwargs):
         # counting starts from 1.
 
         temp = flatten(args)
-        if has_dups(temp):
-            if is_cycle:
-                raise ValueError('there were repeated elements; to resolve '
-                'cycles use Cycle%s.' % ''.join([str(tuple(c)) for c in args]))
-            else:
-                raise ValueError('there were repeated elements.')
+        if has_dups(temp) and not is_cycle:
+            raise ValueError('there were repeated elements.')
         temp = set(temp)
 
         if not is_cycle and \
```

## P06 SKILL | sympy__sympy-12481 | verification-before-completion | changed=13

```diff
diff --git a/sympy/combinatorics/permutations.py b/sympy/combinatorics/permutations.py
index 136ed5a47..6f1c884a8 100755
--- a/sympy/combinatorics/permutations.py
+++ b/sympy/combinatorics/permutations.py
@@ -817,12 +817,15 @@ def __new__(cls, *args, **kwargs):
 
         Permutations entered in cyclic form are converted to array form;
         singletons need not be entered, but can be entered to indicate the
-        largest element:
+        largest element.  Cycles need not be disjoint; they are applied
+        left-to-right:
 
         >>> Permutation([[4, 5, 6], [0, 1]])
         Permutation([1, 0, 2, 3, 5, 6, 4])
         >>> Permutation([[4, 5, 6], [0, 1], [19]])
         Permutation([1, 0, 2, 3, 5, 6, 4], size=20)
+        >>> Permutation([[0, 1], [0, 1]])
+        Permutation([0, 1])
 
         All manipulation of permutations assumes that the smallest element
         is 0 (in keeping with 0-based indexing in Python) so if the 0 is
@@ -895,12 +898,8 @@ def __new__(cls, *args, **kwargs):
         # counting starts from 1.
 
         temp = flatten(args)
-        if has_dups(temp):
-            if is_cycle:
-                raise ValueError('there were repeated elements; to resolve '
-                'cycles use Cycle%s.' % ''.join([str(tuple(c)) for c in args]))
-            else:
-                raise ValueError('there were repeated elements.')
+        if has_dups(temp) and not is_cycle:
+            raise ValueError('there were repeated elements.')
         temp = set(temp)
 
         if not is_cycle and \
```

---


## P07 BASE | scikit-learn__scikit-learn-25232 | test-driven-development | changed=13

```diff
diff --git a/sklearn/impute/_iterative.py b/sklearn/impute/_iterative.py
index 1d918bc0c..cb3e5944e 100644
--- a/sklearn/impute/_iterative.py
+++ b/sklearn/impute/_iterative.py
@@ -117,6 +117,15 @@ class IterativeImputer(_BaseImputer):
         Which strategy to use to initialize the missing values. Same as the
         `strategy` parameter in :class:`~sklearn.impute.SimpleImputer`.
 
+    fill_value : str or numerical value, default=None
+        When `initial_strategy="constant"`, `fill_value` is used to replace all
+        occurrences of missing_values. For string or object data types,
+        `fill_value` must be a string.
+        If `None`, `fill_value` will be 0 when imputing numerical
+        data and "missing_value" for strings or object data types.
+
+        .. versionadded:: 1.3
+
     imputation_order : {'ascending', 'descending', 'roman', 'arabic', \
             'random'}, default='ascending'
         The order in which the features will be imputed. Possible values:
@@ -281,6 +290,7 @@ class IterativeImputer(_BaseImputer):
         "initial_strategy": [
             StrOptions({"mean", "median", "most_frequent", "constant"})
         ],
+        "fill_value": "no_validation",  # any object is valid
         "imputation_order": [
             StrOptions({"ascending", "descending", "roman", "arabic", "random"})
         ],
@@ -301,6 +311,7 @@ class IterativeImputer(_BaseImputer):
         tol=1e-3,
         n_nearest_features=None,
         initial_strategy="mean",
+        fill_value=None,
         imputation_order="ascending",
         skip_complete=False,
         min_value=-np.inf,
@@ -322,6 +333,7 @@ class IterativeImputer(_BaseImputer):
         self.tol = tol
         self.n_nearest_features = n_nearest_features
         self.initial_strategy = initial_strategy
+        self.fill_value = fill_value
         self.imputation_order = imputation_order
         self.skip_complete = skip_complete
         self.min_value = min_value
@@ -613,15 +625,22 @@ class IterativeImputer(_BaseImputer):
             self.initial_imputer_ = SimpleImputer(
                 missing_values=self.missing_values,
                 strategy=self.initial_strategy,
+                fill_value=self.fill_value,
                 keep_empty_features=self.keep_empty_features,
             )
             X_filled = self.initial_imputer_.fit_transform(X)
         else:
             X_filled = self.initial_imputer_.transform(X)
 
-        valid_mask = np.flatnonzero(
-            np.logical_not(np.isnan(self.initial_imputer_.statistics_))
-        )
+        if self.initial_strategy == "constant":
+            # `SimpleImputer` with `strategy="constant"` never discards
+            # features, even when all their values are missing. In particular,
+            # `statistics_` can be all `np.nan` when `fill_value=np.nan`.
+            valid_mask = np.arange(X.shape[1])
+        else:
+            valid_mask = np.flatnonzero(
+                np.logical_not(np.isnan(self.initial_imputer_.statistics_))
+            )
 
         if not self.keep_empty_features:
             # drop empty features
```

## P07 SKILL | scikit-learn__scikit-learn-25232 | test-driven-development | changed=13

```diff
diff --git a/sklearn/impute/_iterative.py b/sklearn/impute/_iterative.py
index 1d918bc0c..b8a479b49 100644
--- a/sklearn/impute/_iterative.py
+++ b/sklearn/impute/_iterative.py
@@ -117,6 +117,15 @@ class IterativeImputer(_BaseImputer):
         Which strategy to use to initialize the missing values. Same as the
         `strategy` parameter in :class:`~sklearn.impute.SimpleImputer`.
 
+    fill_value : str or numerical value, default=None
+        When `initial_strategy="constant"`, `fill_value` is used to replace all
+        occurrences of missing_values. For string or object data types,
+        `fill_value` must be a string.
+        If `None`, `fill_value` will be 0 when imputing numerical
+        data and "missing_value" for strings or object data types.
+
+        .. versionadded:: 1.3
+
     imputation_order : {'ascending', 'descending', 'roman', 'arabic', \
             'random'}, default='ascending'
         The order in which the features will be imputed. Possible values:
@@ -281,6 +290,7 @@ class IterativeImputer(_BaseImputer):
         "initial_strategy": [
             StrOptions({"mean", "median", "most_frequent", "constant"})
         ],
+        "fill_value": "no_validation",  # any object is valid
         "imputation_order": [
             StrOptions({"ascending", "descending", "roman", "arabic", "random"})
         ],
@@ -301,6 +311,7 @@ class IterativeImputer(_BaseImputer):
         tol=1e-3,
         n_nearest_features=None,
         initial_strategy="mean",
+        fill_value=None,
         imputation_order="ascending",
         skip_complete=False,
         min_value=-np.inf,
@@ -322,6 +333,7 @@ class IterativeImputer(_BaseImputer):
         self.tol = tol
         self.n_nearest_features = n_nearest_features
         self.initial_strategy = initial_strategy
+        self.fill_value = fill_value
         self.imputation_order = imputation_order
         self.skip_complete = skip_complete
         self.min_value = min_value
@@ -613,6 +625,7 @@ class IterativeImputer(_BaseImputer):
             self.initial_imputer_ = SimpleImputer(
                 missing_values=self.missing_values,
                 strategy=self.initial_strategy,
+                fill_value=self.fill_value,
                 keep_empty_features=self.keep_empty_features,
             )
             X_filled = self.initial_imputer_.fit_transform(X)
```

---


## P08 BASE | matplotlib__matplotlib-24026 | code-review-and-quality | changed=13

```diff
diff --git a/lib/matplotlib/stackplot.py b/lib/matplotlib/stackplot.py
index c580043eeb..f720253b4f 100644
--- a/lib/matplotlib/stackplot.py
+++ b/lib/matplotlib/stackplot.py
@@ -6,6 +6,8 @@ https://stackoverflow.com/q/2225995/
 (https://stackoverflow.com/users/66549/doug)
 """
 
+import itertools
+
 import numpy as np
 
 from matplotlib import _api
@@ -69,8 +71,10 @@ def stackplot(axes, x, *args,
     y = np.row_stack(args)
 
     labels = iter(labels)
-    if colors is not None:
-        axes.set_prop_cycle(color=colors)
+    if colors is None:
+        colors = axes._get_lines.get_next_color
+    else:
+        colors = itertools.cycle(colors).__next__
 
     # Assume data passed has not been 'stacked', so stack it here.
     # We'll need a float buffer for the upcoming calculations.
@@ -108,7 +112,7 @@ def stackplot(axes, x, *args,
         stack += first_line
 
     # Color between x = 0 and the first array.
-    color = axes._get_lines.get_next_color()
+    color = colors()
     coll = axes.fill_between(x, first_line, stack[0, :],
                              facecolor=color, label=next(labels, None),
                              **kwargs)
@@ -117,7 +121,7 @@ def stackplot(axes, x, *args,
 
     # Color between array i-1 and array i
     for i in range(len(y) - 1):
-        color = axes._get_lines.get_next_color()
+        color = colors()
         r.append(axes.fill_between(x, stack[i, :], stack[i + 1, :],
                                    facecolor=color, label=next(labels, None),
                                    **kwargs))
```

## P08 SKILL | matplotlib__matplotlib-24026 | code-review-and-quality | changed=13

```diff
diff --git a/lib/matplotlib/stackplot.py b/lib/matplotlib/stackplot.py
index c580043eeb..db30f2aeb8 100644
--- a/lib/matplotlib/stackplot.py
+++ b/lib/matplotlib/stackplot.py
@@ -6,6 +6,8 @@ https://stackoverflow.com/q/2225995/
 (https://stackoverflow.com/users/66549/doug)
 """
 
+import itertools
+
 import numpy as np
 
 from matplotlib import _api
@@ -70,7 +72,12 @@ def stackplot(axes, x, *args,
 
     labels = iter(labels)
     if colors is not None:
-        axes.set_prop_cycle(color=colors)
+        # Cycle through the given colors without modifying the Axes property
+        # cycle shared with other plotting methods.
+        colors = itertools.cycle(colors)
+    else:
+        # Consume colors from the Axes property cycle as usual.
+        colors = (axes._get_lines.get_next_color() for _ in itertools.count())
 
     # Assume data passed has not been 'stacked', so stack it here.
     # We'll need a float buffer for the upcoming calculations.
@@ -108,7 +115,7 @@ def stackplot(axes, x, *args,
         stack += first_line
 
     # Color between x = 0 and the first array.
-    color = axes._get_lines.get_next_color()
+    color = next(colors)
     coll = axes.fill_between(x, first_line, stack[0, :],
                              facecolor=color, label=next(labels, None),
                              **kwargs)
@@ -117,7 +124,7 @@ def stackplot(axes, x, *args,
 
     # Color between array i-1 and array i
     for i in range(len(y) - 1):
-        color = axes._get_lines.get_next_color()
+        color = next(colors)
         r.append(axes.fill_between(x, stack[i, :], stack[i + 1, :],
                                    facecolor=color, label=next(labels, None),
                                    **kwargs))
```

---


## P09 BASE | astropy__astropy-14539 | python-anti-patterns | changed=13

```diff
diff --git a/astropy/io/fits/diff.py b/astropy/io/fits/diff.py
index 100cdf1b8..f1e3bfd3a 100644
--- a/astropy/io/fits/diff.py
+++ b/astropy/io/fits/diff.py
@@ -1341,6 +1341,16 @@ class TableDataDiff(_BaseDiff):
 
         super().__init__(a, b)
 
+    def _vla_equal(self, a, b):
+        """Compare two variable-length array values for equality."""
+        a = np.asarray(a)
+        b = np.asarray(b)
+        if a.shape != b.shape:
+            return False
+        if np.issubdtype(a.dtype, np.inexact):
+            return np.allclose(a, b, rtol=self.rtol, atol=self.atol, equal_nan=True)
+        return np.array_equal(a, b)
+
     def _diff(self):
         # Much of the code for comparing columns is similar to the code for
         # comparing headers--consider refactoring
@@ -1449,14 +1459,12 @@ class TableDataDiff(_BaseDiff):
                 arrb.dtype, np.floating
             ):
                 diffs = where_not_allclose(arra, arrb, rtol=self.rtol, atol=self.atol)
-            elif "P" in col.format:
+            elif "P" in col.format or "Q" in col.format:
                 diffs = (
                     [
                         idx
                         for idx in range(len(arra))
-                        if not np.allclose(
-                            arra[idx], arrb[idx], rtol=self.rtol, atol=self.atol
-                        )
+                        if not self._vla_equal(arra[idx], arrb[idx])
                     ],
                 )
             else:
```

## P09 SKILL | astropy__astropy-14539 | python-anti-patterns | changed=13

```diff
diff --git a/astropy/io/fits/diff.py b/astropy/io/fits/diff.py
index 100cdf1b8..60c308c42 100644
--- a/astropy/io/fits/diff.py
+++ b/astropy/io/fits/diff.py
@@ -55,6 +55,15 @@ _COL_ATTRS = [
 ]
 
 
+def _vla_equal(arra, arrb, rtol=0.0, atol=0.0):
+    """Compare two variable-length array column elements."""
+    if arra.shape != arrb.shape:
+        return False
+    if np.issubdtype(arra.dtype, np.number) and np.issubdtype(arrb.dtype, np.number):
+        return np.allclose(arra, arrb, rtol=rtol, atol=atol, equal_nan=True)
+    return np.array_equal(arra, arrb)
+
+
 class _BaseDiff:
     """
     Base class for all FITS diff objects.
@@ -1449,12 +1458,12 @@ class TableDataDiff(_BaseDiff):
                 arrb.dtype, np.floating
             ):
                 diffs = where_not_allclose(arra, arrb, rtol=self.rtol, atol=self.atol)
-            elif "P" in col.format:
+            elif "P" in col.format or "Q" in col.format:
                 diffs = (
                     [
                         idx
                         for idx in range(len(arra))
-                        if not np.allclose(
+                        if not _vla_equal(
                             arra[idx], arrb[idx], rtol=self.rtol, atol=self.atol
                         )
                     ],
```

---


## P10 BASE | sympy__sympy-11618 | python-project-structure | changed=14

```diff
diff --git a/sympy/geometry/point.py b/sympy/geometry/point.py
index 593048464..e83084167 100644
--- a/sympy/geometry/point.py
+++ b/sympy/geometry/point.py
@@ -266,8 +266,10 @@ def distance(self, p):
         sqrt(x**2 + y**2)
 
         """
+        p = Point(p)
         return sqrt(sum([(a - b)**2 for a, b in zip(
-            self.args, p.args if isinstance(p, Point) else p)]))
+            self.args + (S.Zero,)*(len(p) - len(self)),
+            p.args + (S.Zero,)*(len(self) - len(p)))]))
 
     def taxicab_distance(self, p):
         """The Taxicab Distance from self to point p.
@@ -300,7 +302,9 @@ def taxicab_distance(self, p):
 
         """
         p = Point(p)
-        return sum(abs(a - b) for a, b in zip(self.args, p.args))
+        return sum(abs(a - b) for a, b in zip(
+            self.args + (S.Zero,)*(len(p) - len(self)),
+            p.args + (S.Zero,)*(len(self) - len(p))))
 
     def midpoint(self, p):
         """The midpoint between self and point p.
```

## P10 SKILL | sympy__sympy-11618 | python-project-structure | changed=14

```diff
diff --git a/sympy/geometry/point.py b/sympy/geometry/point.py
index 593048464..f6a19acd5 100644
--- a/sympy/geometry/point.py
+++ b/sympy/geometry/point.py
@@ -265,9 +265,19 @@ def distance(self, p):
         >>> p3.distance(Point(0, 0))
         sqrt(x**2 + y**2)
 
+        If the two points have a different number of dimensions the point(s)
+        with fewer coordinates are padded with zeros so that the distance is
+        computed in the space of the larger dimension:
+
+        >>> Point(2, 0).distance(Point(1, 0, 2))
+        sqrt(5)
+
         """
-        return sqrt(sum([(a - b)**2 for a, b in zip(
-            self.args, p.args if isinstance(p, Point) else p)]))
+        p = p.args if isinstance(p, Point) else Point(p).args
+        dim = max(len(self.args), len(p))
+        self_args = self.args + (S.Zero,)*(dim - len(self.args))
+        p_args = p + (S.Zero,)*(dim - len(p))
+        return sqrt(sum([(a - b)**2 for a, b in zip(self_args, p_args)]))
 
     def taxicab_distance(self, p):
         """The Taxicab Distance from self to point p.
```

---


## P11 BASE | django__django-11149 | verification-before-completion | changed=26

```diff
diff --git a/django/contrib/admin/options.py b/django/contrib/admin/options.py
index 880a2cc17b..dea3a5ba5a 100644
--- a/django/contrib/admin/options.py
+++ b/django/contrib/admin/options.py
@@ -2115,27 +2115,35 @@ class InlineModelAdmin(BaseModelAdmin):
         if self.opts.auto_created:
             # We're checking the rights to an auto-created intermediate model,
             # which doesn't have its own individual permissions. The user needs
-            # to have the view permission for the related model in order to
-            # be able to do anything with the intermediate model.
-            return self.has_view_permission(request, obj)
+            # to have the change permission for the related model in order to
+            # be able to add to the intermediate model.
+            return self.has_change_permission(request, obj)
         return super().has_add_permission(request)
 
     def has_change_permission(self, request, obj=None):
         if self.opts.auto_created:
             # We're checking the rights to an auto-created intermediate model,
             # which doesn't have its own individual permissions. The user needs
-            # to have the view permission for the related model in order to
-            # be able to do anything with the intermediate model.
-            return self.has_view_permission(request, obj)
+            # to have the change permission for the related model in order to
+            # be able to change the intermediate model.
+            opts = self.opts
+            # The model was auto-created as intermediary for a
+            # ManyToMany-relationship, find the target model.
+            for field in opts.fields:
+                if field.remote_field and field.remote_field.model != self.parent_model:
+                    opts = field.remote_field.model._meta
+                    break
+            codename = get_permission_codename('change', opts)
+            return request.user.has_perm('%s.%s' % (opts.app_label, codename))
         return super().has_change_permission(request)
 
     def has_delete_permission(self, request, obj=None):
         if self.opts.auto_created:
             # We're checking the rights to an auto-created intermediate model,
             # which doesn't have its own individual permissions. The user needs
-            # to have the view permission for the related model in order to
-            # be able to do anything with the intermediate model.
-            return self.has_view_permission(request, obj)
+            # to have the change permission for the related model in order to
+            # be able to delete from the intermediate model.
+            return self.has_change_permission(request, obj)
         return super().has_delete_permission(request, obj)
 
     def has_view_permission(self, request, obj=None):
```

## P11 SKILL | django__django-11149 | verification-before-completion | changed=26

```diff
diff --git a/django/contrib/admin/options.py b/django/contrib/admin/options.py
index 880a2cc17b..6898932910 100644
--- a/django/contrib/admin/options.py
+++ b/django/contrib/admin/options.py
@@ -2115,27 +2115,31 @@ class InlineModelAdmin(BaseModelAdmin):
         if self.opts.auto_created:
             # We're checking the rights to an auto-created intermediate model,
             # which doesn't have its own individual permissions. The user needs
-            # to have the view permission for the related model in order to
-            # be able to do anything with the intermediate model.
-            return self.has_view_permission(request, obj)
+            # to have the change permission for the related model in order to
+            # be able to add to the intermediate model.
+            return self.has_change_permission(request, obj)
         return super().has_add_permission(request)
 
     def has_change_permission(self, request, obj=None):
         if self.opts.auto_created:
-            # We're checking the rights to an auto-created intermediate model,
-            # which doesn't have its own individual permissions. The user needs
-            # to have the view permission for the related model in order to
-            # be able to do anything with the intermediate model.
-            return self.has_view_permission(request, obj)
+            opts = self.opts
+            # The model was auto-created as intermediary for a many-to-many
+            # Many-relationship; find the target model.
+            for field in opts.fields:
+                if field.remote_field and field.remote_field.model != self.parent_model:
+                    opts = field.remote_field.model._meta
+                    break
+            codename = get_permission_codename('change', opts)
+            return request.user.has_perm('%s.%s' % (opts.app_label, codename))
         return super().has_change_permission(request)
 
     def has_delete_permission(self, request, obj=None):
         if self.opts.auto_created:
             # We're checking the rights to an auto-created intermediate model,
             # which doesn't have its own individual permissions. The user needs
-            # to have the view permission for the related model in order to
-            # be able to do anything with the intermediate model.
-            return self.has_view_permission(request, obj)
+            # to have the change permission for the related model in order to
+            # be able to delete from the intermediate model.
+            return self.has_change_permission(request, obj)
         return super().has_delete_permission(request, obj)
 
     def has_view_permission(self, request, obj=None):
```

---


## P12 BASE | sympy__sympy-24661 | test-driven-development | changed=28

```diff
diff --git a/sympy/parsing/sympy_parser.py b/sympy/parsing/sympy_parser.py
index 52711d1324..1d235a1e28 100644
--- a/sympy/parsing/sympy_parser.py
+++ b/sympy/parsing/sympy_parser.py
@@ -1110,6 +1110,14 @@ class EvaluateFalseTransformer(ast.NodeTransformer):
         ast.BitAnd: 'And',
         ast.BitXor: 'Not',
     }
+    relational_operators = {
+        ast.Eq: 'Eq',
+        ast.NotEq: 'Ne',
+        ast.Lt: 'Lt',
+        ast.LtE: 'Le',
+        ast.Gt: 'Gt',
+        ast.GtE: 'Ge',
+    }
     functions = (
         'Abs', 'im', 're', 'sign', 'arg', 'conjugate',
         'acos', 'acot', 'acsc', 'asec', 'asin', 'atan',
@@ -1186,6 +1194,44 @@ def visit_BinOp(self, node):
             return new_node
         return node
 
+    def visit_Compare(self, node):
+        if not all(op.__class__ in self.relational_operators
+                   for op in node.ops):
+            return self.generic_visit(node)
+
+        left = self.visit(node.left)
+        comparators = [self.visit(comparator)
+                       for comparator in node.comparators]
+
+        relationals = []
+        lhs = left
+        for op, rhs in zip(node.ops, comparators):
+            relationals.append(ast.Call(
+                func=ast.Name(
+                    id=self.relational_operators[op.__class__],
+                    ctx=ast.Load()),
+                args=[lhs, rhs],
+                keywords=[ast.keyword(
+                    arg='evaluate',
+                    value=ast.NameConstant(value=False, ctx=ast.Load()))],
+                starargs=None,
+                kwargs=None,
+            ))
+            lhs = rhs
+
+        if len(relationals) == 1:
+            return relationals[0]
+
+        return ast.Call(
+            func=ast.Name(id='And', ctx=ast.Load()),
+            args=relationals,
+            keywords=[ast.keyword(
+                arg='evaluate',
+                value=ast.NameConstant(value=False, ctx=ast.Load()))],
+            starargs=None,
+            kwargs=None,
+        )
+
     def visit_Call(self, node):
         new_node = self.generic_visit(node)
         if isinstance(node.func, ast.Name) and node.func.id in self.functions:
```

## P12 SKILL | sympy__sympy-24661 | test-driven-development | changed=28

```diff
diff --git a/sympy/parsing/sympy_parser.py b/sympy/parsing/sympy_parser.py
index 52711d1324..75587f52e5 100644
--- a/sympy/parsing/sympy_parser.py
+++ b/sympy/parsing/sympy_parser.py
@@ -1109,6 +1109,12 @@ class EvaluateFalseTransformer(ast.NodeTransformer):
         ast.BitOr: 'Or',
         ast.BitAnd: 'And',
         ast.BitXor: 'Not',
+        ast.Lt: 'Lt',
+        ast.LtE: 'Le',
+        ast.Gt: 'Gt',
+        ast.GtE: 'Ge',
+        ast.Eq: 'Eq',
+        ast.NotEq: 'Ne',
     }
     functions = (
         'Abs', 'im', 're', 'sign', 'arg', 'conjugate',
@@ -1186,6 +1192,28 @@ def visit_BinOp(self, node):
             return new_node
         return node
 
+    def visit_Compare(self, node):
+        if len(node.ops) > 1:
+            # SymPy has no way of representing chained comparisons as a
+            # single object, so raise rather than silently reinterpreting
+            # the expression.
+            raise NotImplementedError(
+                "Cannot parse chained comparisons with evaluate=False")
+        op = node.ops[0]
+        if op.__class__ in self.operators:
+            sympy_class = self.operators[op.__class__]
+            right = self.visit(node.comparators[0])
+            left = self.visit(node.left)
+            new_node = ast.Call(
+                func=ast.Name(id=sympy_class, ctx=ast.Load()),
+                args=[left, right],
+                keywords=[ast.keyword(arg='evaluate', value=ast.NameConstant(value=False, ctx=ast.Load()))],
+                starargs=None,
+                kwargs=None
+            )
+            return new_node
+        return node
+
     def visit_Call(self, node):
         new_node = self.generic_visit(node)
         if isinstance(node.func, ast.Name) and node.func.id in self.functions:
```

---


## P13 BASE | sphinx-doc__sphinx-7440 | code-review-and-quality | changed=30

```diff
diff --git a/doc/extdev/index.rst b/doc/extdev/index.rst
index 8c909e315..266da52b7 100644
--- a/doc/extdev/index.rst
+++ b/doc/extdev/index.rst
@@ -27,7 +27,7 @@ Discovery of builders by entry point
 
 .. versionadded:: 1.6
 
-:term:`Builder` extensions can be discovered by means of `entry points`_ so
+:term:`builder` extensions can be discovered by means of `entry points`_ so
 that they do not have to be listed in the :confval:`extensions` configuration
 value.
 
diff --git a/sphinx/domains/std.py b/sphinx/domains/std.py
index d820cfe5c..95f896563 100644
--- a/sphinx/domains/std.py
+++ b/sphinx/domains/std.py
@@ -305,7 +305,7 @@ def make_glossary_term(env: "BuildEnvironment", textnodes: Iterable[Node], index
         term['ids'].append(node_id)
 
     std = cast(StandardDomain, env.get_domain('std'))
-    std.note_object('term', termtext.lower(), node_id, location=term)
+    std.note_object('term', termtext, node_id, location=term)
 
     # add an index entry too
     indexnode = addnodes.index()
@@ -565,7 +565,7 @@ class StandardDomain(Domain):
         # links to tokens in grammar productions
         'token':   TokenXRefRole(),
         # links to terms in glossary
-        'term':    XRefRole(lowercase=True, innernodeclass=nodes.inline,
+        'term':    XRefRole(innernodeclass=nodes.inline,
                             warn_dangling=True),
         # links to headings or arbitrary labels
         'ref':     XRefRole(lowercase=True, innernodeclass=nodes.inline,
@@ -952,8 +952,6 @@ class StandardDomain(Domain):
         # all others
         for objtype in self.object_types:
             key = (objtype, target)
-            if objtype == 'term':
-                key = (objtype, ltarget)
             if key in self.objects:
                 docname, labelid = self.objects[key]
                 results.append(('std:' + self.role_for_objtype(objtype),
```

## P13 SKILL | sphinx-doc__sphinx-7440 | code-review-and-quality | changed=30

```diff
diff --git a/sphinx/domains/std.py b/sphinx/domains/std.py
index d820cfe5c..59f4ac877 100644
--- a/sphinx/domains/std.py
+++ b/sphinx/domains/std.py
@@ -305,7 +305,7 @@ def make_glossary_term(env: "BuildEnvironment", textnodes: Iterable[Node], index
         term['ids'].append(node_id)
 
     std = cast(StandardDomain, env.get_domain('std'))
-    std.note_object('term', termtext.lower(), node_id, location=term)
+    std.note_object('term', termtext, node_id, location=term)
 
     # add an index entry too
     indexnode = addnodes.index()
@@ -565,8 +565,7 @@ class StandardDomain(Domain):
         # links to tokens in grammar productions
         'token':   TokenXRefRole(),
         # links to terms in glossary
-        'term':    XRefRole(lowercase=True, innernodeclass=nodes.inline,
-                            warn_dangling=True),
+        'term':    XRefRole(innernodeclass=nodes.inline, warn_dangling=True),
         # links to headings or arbitrary labels
         'ref':     XRefRole(lowercase=True, innernodeclass=nodes.inline,
                             warn_dangling=True),
@@ -923,13 +922,27 @@ class StandardDomain(Domain):
         return make_refnode(builder, fromdocname, docname,
                             labelid, contnode)
 
+    def _get_object(self, objtype: str, target: str) -> Tuple[str, str]:
+        """Get the entry for *target* if it exists.
+
+        Object names are case-sensitive, but glossary terms can also be
+        referenced case-insensitively.
+        """
+        if (objtype, target) in self.objects:
+            return self.objects[objtype, target]
+        elif objtype == 'term':
+            for (_type, name), entry in self.objects.items():
+                if _type == 'term' and name.lower() == target.lower():
+                    return entry
+        return '', ''
+
     def _resolve_obj_xref(self, env: "BuildEnvironment", fromdocname: str,
                           builder: "Builder", typ: str, target: str,
                           node: pending_xref, contnode: Element) -> Element:
         objtypes = self.objtypes_for_role(typ) or []
         for objtype in objtypes:
-            if (objtype, target) in self.objects:
-                docname, labelid = self.objects[objtype, target]
+            docname, labelid = self._get_object(objtype, target)
+            if docname:
                 break
         else:
             docname, labelid = '', ''
@@ -951,11 +964,8 @@ class StandardDomain(Domain):
                 results.append(('std:' + role, res))
         # all others
         for objtype in self.object_types:
-            key = (objtype, target)
-            if objtype == 'term':
-                key = (objtype, ltarget)
-            if key in self.objects:
-                docname, labelid = self.objects[key]
+            docname, labelid = self._get_object(objtype, target)
+            if docname:
                 results.append(('std:' + self.role_for_objtype(objtype),
                                 make_refnode(builder, fromdocname, docname,
                                              labelid, contnode)))
```

---


## P14 BASE | pytest-dev__pytest-7432 | python-anti-patterns | changed=26

```diff
diff --git a/src/_pytest/skipping.py b/src/_pytest/skipping.py
index 7bd975e5a..591a65df9 100755
--- a/src/_pytest/skipping.py
+++ b/src/_pytest/skipping.py
@@ -291,7 +291,8 @@ def pytest_runtest_makereport(item: Item, call: CallInfo[None]):
             else:
                 rep.outcome = "passed"
                 rep.wasxfail = xfailed.reason
-    elif (
+
+    if (
         item._store.get(skipped_by_mark_key, True)
         and rep.skipped
         and type(rep.longrepr) is tuple
```

## P14 SKILL | pytest-dev__pytest-7432 | python-anti-patterns | changed=26

```diff
diff --git a/src/_pytest/skipping.py b/src/_pytest/skipping.py
index 7bd975e5a..e2595c07c 100755
--- a/src/_pytest/skipping.py
+++ b/src/_pytest/skipping.py
@@ -262,6 +262,20 @@ def pytest_runtest_makereport(item: Item, call: CallInfo[None]):
     outcome = yield
     rep = outcome.get_result()
     xfailed = item._store.get(xfailed_key, None)
+
+    # skipped by mark.skipif; change the location of the failure
+    # to point to the item definition, otherwise it will display
+    # the location of where the skip exception was raised within pytest
+    if (
+        item._store.get(skipped_by_mark_key, True)
+        and rep.skipped
+        and type(rep.longrepr) is tuple
+    ):
+        _, _, reason = rep.longrepr
+        filename, line = item.reportinfo()[:2]
+        assert line is not None
+        rep.longrepr = str(filename), line + 1, reason
+
     # unittest special case, see setting of unexpectedsuccess_key
     if unexpectedsuccess_key in item._store and rep.when == "call":
         reason = item._store[unexpectedsuccess_key]
@@ -291,18 +305,6 @@ def pytest_runtest_makereport(item: Item, call: CallInfo[None]):
             else:
                 rep.outcome = "passed"
                 rep.wasxfail = xfailed.reason
-    elif (
-        item._store.get(skipped_by_mark_key, True)
-        and rep.skipped
-        and type(rep.longrepr) is tuple
-    ):
-        # skipped by mark.skipif; change the location of the failure
-        # to point to the item definition, otherwise it will display
-        # the location of where the skip exception was raised within pytest
-        _, _, reason = rep.longrepr
-        filename, line = item.reportinfo()[:2]
-        assert line is not None
-        rep.longrepr = str(filename), line + 1, reason
 
 
 def pytest_report_teststatus(report: BaseReport) -> Optional[Tuple[str, str, str]]:
```

---


## P15 BASE | django__django-14053 | django-tdd | changed=28

```diff
diff --git a/django/contrib/staticfiles/storage.py b/django/contrib/staticfiles/storage.py
index 494890cc23..c6c1088d0f 100644
--- a/django/contrib/staticfiles/storage.py
+++ b/django/contrib/staticfiles/storage.py
@@ -226,17 +226,28 @@ class HashedFilesMixin:
             path for path in paths
             if matches_patterns(path, self._patterns)
         ]
+        # Adjustable files to yield at the end, keyed by the original name.
+        processed_adjustable_paths = {}
         # Do a single pass first. Post-process all files once, then repeat for
         # adjustable files.
         for name, hashed_name, processed, _ in self._post_process(paths, adjustable_paths, hashed_files):
-            yield name, hashed_name, processed
+            if isinstance(processed, Exception):
+                yield name, hashed_name, processed
+                return
+            if name in adjustable_paths:
+                processed_adjustable_paths[name] = (name, hashed_name, processed)
+            else:
+                yield name, hashed_name, processed
 
         paths = {path: paths[path] for path in adjustable_paths}
 
         for i in range(self.max_post_process_passes):
             substitutions = False
             for name, hashed_name, processed, subst in self._post_process(paths, adjustable_paths, hashed_files):
-                yield name, hashed_name, processed
+                if isinstance(processed, Exception):
+                    yield name, hashed_name, processed
+                    return
+                processed_adjustable_paths[name] = (name, hashed_name, processed)
                 substitutions = substitutions or subst
 
             if not substitutions:
@@ -248,6 +259,9 @@ class HashedFilesMixin:
         # Store the processed paths
         self.hashed_files.update(hashed_files)
 
+        for name, hashed_name, processed in processed_adjustable_paths.values():
+            yield name, hashed_name, processed
+
     def _post_process(self, paths, adjustable_paths, hashed_files):
         # Sort the files by directory level
         def path_level(name):
```

## P15 SKILL | django__django-14053 | django-tdd | changed=28

```diff
diff --git a/django/contrib/staticfiles/storage.py b/django/contrib/staticfiles/storage.py
index 494890cc23..f01b01b6c6 100644
--- a/django/contrib/staticfiles/storage.py
+++ b/django/contrib/staticfiles/storage.py
@@ -226,22 +226,42 @@ class HashedFilesMixin:
             path for path in paths
             if matches_patterns(path, self._patterns)
         ]
-        # Do a single pass first. Post-process all files once, then repeat for
-        # adjustable files.
+
+        # Adjustable files may be processed several times until the references
+        # between them are resolved. Postpone yielding them until the end so
+        # that each file is reported only once, with its final hashed name.
+        processed_adjustable_paths = {}
+
+        # Do a single pass first. Post-process all files once, yielding not
+        # adjustable files now, and postponing adjustable file processing to
+        # after all files are copied.
         for name, hashed_name, processed, _ in self._post_process(paths, adjustable_paths, hashed_files):
-            yield name, hashed_name, processed
+            if name in adjustable_paths:
+                if isinstance(processed, Exception):
+                    yield name, None, processed
+                else:
+                    processed_adjustable_paths[name] = (hashed_name, processed)
+            else:
+                yield name, hashed_name, processed
 
         paths = {path: paths[path] for path in adjustable_paths}
 
+        substitutions = False
         for i in range(self.max_post_process_passes):
             substitutions = False
             for name, hashed_name, processed, subst in self._post_process(paths, adjustable_paths, hashed_files):
-                yield name, hashed_name, processed
+                if isinstance(processed, Exception):
+                    yield name, None, processed
+                else:
+                    processed_adjustable_paths[name] = (hashed_name, processed)
                 substitutions = substitutions or subst
 
             if not substitutions:
                 break
 
+        for name, (hashed_name, processed) in processed_adjustable_paths.items():
+            yield name, hashed_name, processed
+
         if substitutions:
             yield 'All', None, RuntimeError('Max post-process passes exceeded.')
```

---
