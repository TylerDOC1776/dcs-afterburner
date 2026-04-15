keep the mission source in normal folders in the repo,
have a build job assemble those files into the expected mission package layout,
zip that layout into a .miz,
upload it as a workflow artifact, and optionally
publish it as a GitHub release asset. GitHub Actions supports manual triggers with workflow_dispatch, passing files between jobs with artifacts, and attaching built files to releases.
Practical structure

A solid repo layout would be something like:

mission-src/
  Init/
  Scripts/
  Moose/
  Mist/
  CTLD/
  l10n/
  options/
build/
tools/
.github/workflows/

Then the pipeline builds:

dist/MyMission-v1.2.3.miz
The important caveat

This only works cleanly if you define a source-of-truth build layout.

For DCS missions, the safest pattern is usually:

keep a known-good base mission package or extracted mission folder,
replace or inject the generated Lua/scripts during CI,
then rebuild the .miz.

That avoids trying to regenerate every mission-side file from scratch and accidentally producing a package that is syntactically valid as a zip but wrong for DCS.

Best pipeline design

I would split it into three workflows or three jobs in one workflow.

1. Validate

Runs on push and pull request.

It should:

lint Lua
run your custom DCS checks
optionally run benchmark-lite on the linter itself
2. Build mission package

Runs on tag push or manual dispatch.

It should:

check out the repo
stage a clean build directory
copy the base mission contents
inject updated scripts
generate version metadata
package everything into .miz
upload the .miz as an artifact

Artifacts are the right way to persist the built package from the workflow.

3. Release

Runs on tags, or after a successful build job.

It should:

download the built .miz artifact
create or update a GitHub release
attach the .miz file to that release

GitHub’s release flow and release asset upload API support exactly that pattern.

What I would actually build

Use a manual-and-tag-driven release workflow.

Trigger it with:

workflow_dispatch for test builds
push.tags for actual release builds

That gives you:

test packaging on demand
stable release packaging on version tags

GitHub documents workflow_dispatch for manual runs, and workflows can be configured around those triggers.

Recommended build logic

Your builder script should do this in order:

1. Clean dist/ and tmp/
2. Copy base mission template to tmp/mission/
3. Copy repo-managed Lua/scripts into tmp/mission/
4. Inject version/build info
5. Validate required files exist
6. Package tmp/mission/ into dist/<name>.miz
7. Emit checksum

That validation step matters. The build should fail if required files are missing, duplicated, or placed in the wrong path.

Best way to manage the source mission

You have two realistic options.

Option A — Store an extracted mission tree in git

This is best if:

multiple files are changing regularly
you want diffable content
you want CI to assemble the package from readable sources

This is usually the better long-term choice.

Option B — Store a base .miz and patch it during CI

This is best if:

only a few Lua files change
the rest of the mission structure is mostly static

This is simpler at first, but worse for maintenance if the mission grows.

For your use case, with linting and planned static analysis, Option A is better.

Release naming

Use deterministic names, for example:

Goonfront-Caucasus-v1.4.0.miz
Goonfront-Caucasus-main+sha-abc1234.miz

That makes artifacts and releases much easier to track.

Good extra outputs

Have the workflow also generate:

SHA256 checksum
build manifest
release notes stub
lint summary

Then upload all of them as artifacts, and optionally include them in the release. GitHub artifacts are designed for storing files produced by a workflow.

Good failure gates

The build job should stop if:

lint fails
required mission files are missing
duplicate injected scripts are found
package output is empty or unusually small
version tag and embedded version disagree

That keeps “bad but zipped” missions from being published.

Example workflow skeleton
name: build-miz

on:
  workflow_dispatch:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Prepare build dirs
        run: |
          rm -rf dist tmp
          mkdir -p dist tmp/mission

      - name: Stage mission files
        run: |
          cp -R mission-base/* tmp/mission/
          cp -R mission-src/* tmp/mission/

      - name: Validate mission layout
        run: |
          test -f tmp/mission/mission
          test -d tmp/mission/Scripts

      - name: Build miz
        run: |
          cd tmp/mission
          zip -r ../../dist/Goonfront-Caucasus-${GITHUB_REF_NAME:-dev}.miz .

      - name: Checksum
        run: |
          sha256sum dist/*.miz > dist/SHA256SUMS.txt

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: miz-build
          path: dist/

Then a release job can either call the GitHub API or use a release action to attach the .miz artifact to a release. GitHub supports both release creation and asset upload for built files.

Where this fits in your broader plan

Your full CI/CD stack can be:

ci-lint.yml → Lua lint + DCS rules
benchmark.yml → parser/linter performance tracking
build-miz.yml → assemble mission package
release.yml → publish tagged .miz

That is a solid progression:
validate first, package second, publish last.
