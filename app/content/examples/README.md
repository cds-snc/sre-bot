# Content examples

Example provisioned-content files, one per kind, validated by `make check-content-schemas`
and read as the content root in the `local` and `ci` environments.

- Layout: `<owner>/<kind>/[<folder>/...]<id>.yaml`, the same as a deployment's content root.
- Every file starts with `kind: <owner>/<kind>`, an integer `version` and its `id` (the file name without `.yaml`).
- Use `example.com` addresses and invented names only; never put organisation data, tokens or secrets here.
- To add one: write the file under the kind's directory, then run `make check-content-schemas`.
  After changing a kind's file model, run `make export-content-schemas` to regenerate `content/schemas/`.
