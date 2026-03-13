# CI Additions — Future Considerations

Possible workflows to add as the project matures.

---

## Mission lint dogfood

Once `afterburner analyze` is functional, run it against the fixture `.miz` files on every push. Catches regressions where the tool crashes or returns unexpected results on known inputs.

```yaml
name: Mission Lint Dogfood

on: [push, pull_request]

jobs:
  dogfood:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .
      - name: Lint fixture missions
        run: |
          for f in tests/fixtures/*.miz; do
            afterburner analyze "$f" --json
          done
```

---

## Release automation

On a `v*` tag push, build a wheel and create a GitHub Release with it attached. Add once the tool is ready for distribution.

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build
      - run: python -m build
      - name: Create release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/*
```

---

## Coverage reporting

Extend the existing coverage step to upload a report to Codecov for trend tracking across PRs. Useful once the test suite is substantial.

```yaml
- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
```

Add after the `pytest --cov` step in `ci.yml`.

---

## PyPI publish

Publish to PyPI automatically on release. Only relevant if the tool goes public.

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

Uses trusted publishing (no API token needed).
