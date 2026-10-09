# Development and integration workflow

I use a small iterative process with explicit quality gates. The wider local
workbench remains a proposed system; each increment must expose its own verified
contract before integration.

| Gate | Evidence | Acceptance |
| --- | --- | --- |
| Requirements | Issue with inputs, outputs, risk and expected behaviour | Scope fits English local timing transfer |
| Design | Contract, algorithm choice, resource estimate | Bounded memory; dependency choice justified |
| Implementation | Branch changes and unit/integration checks | Invalid input cannot silently produce misleading timings |
| Integration | Ruff, pytest, wheel and installed-wheel demo | Both CI Python versions pass |
| Delivery | Reviewed tag, wheel and retained run artifacts | Public repository links and execution evidence available |

Use short feature branches, meaningful commits and pull requests with a concrete
before/after behaviour. Do not merge failing gates. Review is planned when a
reviewer is available; no peer review is asserted from a pull request alone.

Python is selected for scientific ecosystem access. NumPy supplies transparent
numeric arrays without a model runtime. Python's `wave`, `argparse` and `json`
cover the strict input and CLI contract. Librosa/PyTorch are deferred until
speech features or a model backend require them. Ruff provides a single fast
lint gate; pytest exercises numeric oracles and error boundaries. `uv.lock` makes
dependency resolution explicit; hatchling builds the src-layout wheel.

Git records code, tests, lockfile and documentation. Generated large audio,
model weights and private data stay outside Git; their manifests retain hashes.
GitHub provides repository hosting, issues and Actions runs. CI delivery produces
versioned build artifacts; publishing a Python package index release is a later
decision. The workflow grants only read access to repository contents.
