# Retained research skill sources

`arthera/` contains two complete, unchanged skill folders from
[artherahq/skills](https://github.com/artherahq/skills) at commit
`825040f3cc7eb4179a8ee86e0158d9828f427f7b`, plus the upstream Apache-2.0
`LICENSE`. Every retained file is hashed in `import_manifest.json`.

These are attributed source references. They are outside `.agents/skills/`
and are not automatically loaded as active agent instructions. The local
Zenith adapters own their application to this repository; read
[`docs/skills.md`](../../docs/skills.md).

The original folders include illustrative programs and tests. No upstream
program has been executed or installed as part of this import. They require
numpy and pandas; the original historical benchmark needs neither. Importing
these files does not add those dependencies or permit shell commands,
network access, arbitrary output writes, or execution of the original
SKILL.md's “run now” instructions.

For an update, select a new immutable upstream commit, review the changed
instructions and executable files, preserve complete folders and license,
refresh file hashes, and review each local adapter against the native
contracts. Do not silently replace retained source from a moving branch.

Karpathy's [autoresearch program](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md)
was inspected as methodological prior art. Its source is not copied here:
the inspected README states MIT, but the pinned repository has no LICENSE
or LICENSE.md file. Its reference-only pin and rights observation are in
the manifest. Zenith's experiment instructions are locally authored and
do not install its GPU training stack.
