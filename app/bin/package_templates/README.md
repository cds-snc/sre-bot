# Package templates

`bin/new_package.py` (`make new-package`) fills these with `string.Template` to
create a package in the shape of decisions/feature-packages.md's layout table.

- A template's file name never decides the generated name: the kind matrix in
  `new_package.py` maps each template to its path.
- Renaming or adding a generated file means the layout table allows it; amend
  the table in decisions/feature-packages.md and its machine copy,
  `bin/package_layout.toml`, in the same change (a drift test fails otherwise).
  The shape check reads the manifest, so it needs no edit.
- `$name` placeholders are substituted; write `$$` for a literal `$`.
