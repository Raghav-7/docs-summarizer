# GitHub Actions CI & Offline Testing Guide

This guide explains how Continuous Integration (CI) is implemented in `Raghav-7/docs-summarizer`, the structure of the automated workflow, the design of the offline test suite, and how to monitor workflow runs in GitHub.

---

## 1. Core Concepts in GitHub Actions

GitHub Actions is an automation platform built directly into GitHub. It executes code upon events occurring in your repository.

```
Repository Event (push / PR / manual)
        │
        ▼
   Workflow (.github/workflows/ci.yml)
        │
        ▼
   Runner (GitHub-hosted ubuntu-latest VM)
        │
        ▼
   Job (Run Offline Unit & Integration Tests)
        ├── Step 1: Checkout Repository
        ├── Step 2: Set up Python 3.11 (with pip cache)
        ├── Step 3: Install Dependencies
        └── Step 4: Execute Test Suite
```

* **Workflow:** An automated process defined in a YAML file under `.github/workflows/`.
* **Triggers (`on`):** Events that initiate the workflow:
  * `push`: Runs automatically whenever new commits are pushed to `main` or feature branches (`feat/**`).
  * `pull_request`: Runs automatically when a PR targeting `main` is opened or updated.
  * `workflow_dispatch`: Enables a manual **"Run workflow"** button directly in the GitHub web interface.
* **Runner:** The virtual machine environment that executes your jobs. `ubuntu-latest` provides a clean, sandboxed Ubuntu Linux VM managed by GitHub at zero cost for public repositories.
* **Permissions (`permissions`):** Security boundaries governing what GitHub's temporary authentication token (`GITHUB_TOKEN`) can access. Setting `contents: read` enforces the **Principle of Least Privilege**, preventing CI from modifying repository code or tags.
* **Concurrency (`concurrency`):** Cancels older in-progress workflow runs on the same branch if a newer commit is pushed, saving runner minutes and avoiding outdated test results.

---

## 2. CI Workflow Structure (`.github/workflows/ci.yml`)

```yaml
name: Docs Summarizer CI

on:
  push:
    branches: [ main, 'feat/**' ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: Run Offline Unit & Integration Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v7

      - name: Set up Python 3.11
        uses: actions/setup-python@v7
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Execute Offline Test Suite
        env:
          APP_SECRET_KEY: ci-test-secret-key-12345
          GEMINI_API_KEY: ""
          GROQ_API_KEY: ""
        run: |
          python -m unittest discover -s tests -v
```

---

## 3. Offline Test Architecture (`tests/`)

### Why CI Tests Must Run Offline
1. **Zero External Costs:** Calling live AI APIs (Gemini/Groq) in CI incurs usage costs or consumes daily quota.
2. **Determinism:** Live network calls can experience timeouts, latency spikes, or quota limits (`HTTP 429`), leading to flaky test failures unrelated to code quality.
3. **Security:** Real API keys and private chat exports are never checked into git or exposed in CI logs.

### Test Modules

1. **`tests/test_parser.py` (Parsing Logic):**
   * Verifies regex extraction of Android WhatsApp timestamps and messages.
   * Verifies regex extraction of iOS square-bracket timestamp format.
   * Tests empty file handling, missing file paths, and filtering of non-chat lines.
2. **`tests/test_app_offline.py` (Flask Client & Integration):**
   * Validates `TOOLS` dictionary schema and definitions.
   * Tests `/tool/<tool_name>` page routes.
   * Tests rejection of unknown tools (HTTP 400).
   * Tests `/api/tool/statistics/stats` error handling (empty files, garbage files).
   * Tests `/api/tool/statistics/stats` and `/api/tool/summarize/stats` with synthetic in-memory `.txt` and `.zip` files.
   * Tests `/api/tool/summarize` using `unittest.mock.patch` to verify the controller response pipeline without contacting Google servers.

---

## 4. How to Inspect Workflow Runs on GitHub

Once you push this branch and open a PR:

1. **Navigate to GitHub:** Open [https://github.com/Raghav-7/docs-summarizer](https://github.com/Raghav-7/docs-summarizer).
2. **Open the Actions Tab:** Click the **Actions** tab at the top of the repository page.
3. **Select the Workflow:** In the left sidebar, click **Docs Summarizer CI**.
4. **View Run Details:**
   * Each commit shows a run entry with its commit message, author, branch, and status icon:
     * Green checkmark (✔) = Passed
     * Red cross (✖) = Failed
     * Yellow circle (●) = In progress
5. **Inspect Step Logs:**
   * Click on a run to open its summary page.
   * Under **Jobs**, click **Run Offline Unit & Integration Tests**.
   * Expand any step (e.g. `Execute Offline Test Suite`) to view the exact console output and test durations.
6. **Triggering Manually (`workflow_dispatch`):**
   * Under **Actions** -> **Docs Summarizer CI**, you will see a blue banner: **"Run workflow"**.
   * Select your branch and click the green **Run workflow** button to execute CI on demand.

