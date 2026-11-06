# Package templates

`bin/new_package.py` (`make new-package`) fills these with `string.Template` to
create a package in the shape of decisions/feature-packages.md's layout table.

- A template's file name never decides the generated name: the kind matrix in
  `new_package.py` maps each template to its path.
- Renaming or adding a generated file means the layout table allows it; update
  the table (by amending feature-packages.md) and `bin/check_package_shape.py`
  in the same change, or every new package fails the shape check.
- `$name` placeholders are substituted; write `$$` for a literal `$`.
