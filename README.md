# AAAgentBench

AAAgentBench is a small benchmark harness for evaluating agent solvers on CTF-style tasks.

## Environment

This project uses `uv`.

Setup:

```bash
cd AAAgentBench
uv sync
```

Run the CLI:

```bash
uv run python -m src.run --help
```

## Available Platforms

- `nyu`: NYU CTF Bench via the `nyuctf` package

## Available Solvers

- `codex`: runs `codex exec` non-interactively and validates flags automatically
- `manual`: simple interactive solver for testing
- `pentestgpt`: runs the PentestGPT Docker container in non-interactive mode against NYU targets and validates any captured flags automatically

## Usage

Run a single testcase:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver codex \
  --testcase 2017q-cry-almost_xor \
  --split test \
  --timeout-sec 3600
```

Run all testcases in a split:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver codex \
  --run-all \
  --split test
```

Run all testcases listed in a file:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver pentestgpt \
  --target-list-file ./targets.txt \
  --timeout-sec 300
```

The list file should contain one canonical target id per line. Blank lines and lines starting with `#` are ignored.

Useful options:

- `--platform`: select platform implementation
- `--solver`: select solver implementation
- `--testcase`: run one target id
- `--target-list-file`: run all target ids listed in a text file
- `--run-all`: run the whole selected split
- `--category`: when used with `--run-all`, only run the selected category; can be passed multiple times
- `--save-result`: save one testcase result locally
- `--logs-dir`: choose where per-target runtime logs are stored
- `--disable-run-logs`: disable per-target runtime logs
- `--results-dir`: choose where local result files are stored
- `--summary-from-results`: summarize saved testcase results without rerunning
- `--force-rerun`: ignore cached saved results and rerun targets
- `--split`: dataset split, usually `test` or `development`
- `--timeout-sec`: per-target timeout
- `--log-level`: logging verbosity
- `--model`: model name for `codex` or `pentestgpt`
- `--max-attempts`: retry count for solvers that support it
- `--sandbox-mode`: Codex sandbox mode

### Using PentestGPT

`pentestgpt` expects a running PentestGPT Docker container and invokes `pentestgpt --non-interactive` inside that container. Each AAAgentBench run uses a target-scoped workspace under `/workspace/aaagentbench/<target_id>`, and the solver clears that target directory before each run to avoid stale benchmark artifacts affecting results. For NYU targets:

- service-backed challenges are exposed to PentestGPT as `http://host.docker.internal:<port>` (on native Linux Docker Engine you may need to start the container with `--add-host=host.docker.internal:host-gateway` for this hostname to resolve)
- attachment-only challenges are mirrored into a shared workspace path under `/workspace/aaagentbench/<target_id>`
- PentestGPT is started with its process working directory set to that target-specific workspace so it stays scoped to the current challenge files
- the NYU platform automatically creates the external `ctfnet` Docker network when required by challenge compose files

Example runs:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver pentestgpt \
  --testcase 2021f-rev-maze \
  --timeout-sec 300

uv run python -m src.run \
  --platform nyu \
  --solver pentestgpt \
  --testcase 2021f-cry-collision_course \
  --timeout-sec 300
```

PentestGPT-specific options:

- `--pentestgpt-container-name`: Docker container name, default `pentestgpt`
- `--pentestgpt-auth-mode`: auth mode passed into the container, default `openrouter`
- `--pentestgpt-shared-workspace-host-root`: host directory mirrored into the PentestGPT container for static targets
- `--pentestgpt-shared-workspace-container-root`: container path for the shared workspace, default `/workspace/aaagentbench`
- `--pentestgpt-anthropic-base-url`: `ANTHROPIC_BASE_URL` passed into PentestGPT
- `--pentestgpt-anthropic-auth-token`: `ANTHROPIC_AUTH_TOKEN` passed into PentestGPT

Detailed runtime logs:

- AAAgentBench writes one runtime log per target under `logs/<platform>/<solver>/<target_id>.log` by default
- before each run, the solver clears the current target workspace under `/workspace/aaagentbench/<target_id>` so leftover files from earlier runs do not leak into the session
- log lines are timestamped and preserve PentestGPT non-interactive CLI output, including the target/context banner, final walkthrough text, discovered flags, session id, and total cost
- unlike the standalone raw runner, these logs are not guaranteed to contain raw event markers such as `[STATE]`, `[TOOL]`, or `[DONE]`
- the saved result JSON also includes the `log_path` for each target

Example with logs and saved results:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver pentestgpt \
  --target-list-file ./targets.txt \
  --timeout-sec 300 \
  --save-result \
  --results-dir ./results \
  --logs-dir ./logs
```

## Adding a Solver

1. Add a new solver class under [solver](src/solver).
2. Implement the interface in [solver/base.py](src/solver/base.py).
3. Register the solver name in [solver/\_\_init\_\_.py](src/solver/__init__.py).
4. Expose any solver-specific CLI options in [run.py](src/run.py) if needed.

Minimal interface:

```python
class BaseSolver(ABC):
    @abstractmethod
    def solve(
        self,
        session: Session,
        submit_flag: Callable[[str], ValidationResult],
    ) -> SolveResult:
        ...
```

Return:

- `SolveResult(status="solved", flag=...)` when a valid flag is found
- `SolveResult(status="give_up", flag=None)` when the solver cannot finish

## Saving Single-Run Results

Save one testcase result:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver codex \
  --testcase 2017q-cry-almost_xor \
  --save-result
```

This writes a JSON file to:

```text
results/<platform>/<solver>/<target_id>.json
```

Summarize saved single-target results later:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver codex \
  --summary-from-results
```

This is useful when you run a few cases manually and want to compute summary statistics later without rerunning them.

If you use `--save-result`, both single-target runs and `--run-all` will reuse existing saved results instead of rerunning the same testcase.

To ignore cache and rerun:

```bash
uv run python -m src.run \
  --platform nyu \
  --solver codex \
  --testcase 2017q-cry-almost_xor \
  --save-result \
  --force-rerun
```
