# Contributing Guide

Thank you for your interest in contributing! This is a research/scientific tool and we welcome contributions of all kinds — whether you've found a bug, have an idea for a new feature, want to improve the docs, or are submitting code. **No contribution is too small.**

---

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)
- [Improving Documentation](#improving-documentation)
- [Submitting Code Changes](#submitting-code-changes)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Questions & Discussions](#questions--discussions)

---

## Ways to Contribute

| Type | Where |
|------|--------|
| 🐛 Report a bug | [Open a bug report](../../issues/new?template=bug_report.yml) |
| 💡 Request a feature | [Open a feature request](../../issues/new?template=feature_request.yml) |
| 📝 Improve documentation | Edit files directly and open a PR |
| 🔧 Submit a code fix or feature | Fork → branch → PR |

---

## Reporting Bugs

If something isn't working as expected, please open a **bug report** using the issue template. The more detail you can provide, the faster we can investigate:

- What you were trying to do
- What actually happened (error message, unexpected output)
- Steps to reproduce
- Your environment (OS, Python version, relevant package versions)

You don't need to have a fix ready — just a clear description helps a lot.

---

## Requesting Features

Have an idea that would make this tool more useful for your research? Open a **feature request**. Describe:

- The problem you're trying to solve
- What you'd like to see
- Any relevant context (dataset types, workflows, related tools)

We love hearing how people are using the tool in practice.

---

## Improving Documentation

Documentation improvements are always welcome and are a great first contribution. This includes:

- Fixing typos or unclear wording
- Adding usage examples
- Improving docstrings
- Expanding the README

For small edits (typos, a sentence or two), feel free to open a PR directly without an issue.

---

## Submitting Code Changes

### 1. Find or open an issue

Before writing code, check if there's an existing issue for what you want to work on. If not, open one so we can discuss the approach first — this avoids wasted effort.

### 2. Fork and clone

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/janti001/PickMe
cd PickMe
```

### 3. Create a branch

Use a short, descriptive branch name:

```bash
git checkout -b fix/membrane-segmentation-crash
git checkout -b feature/add-export-format
git checkout -b docs/update-installation-guide
```

### 4. Make your changes

See [Development Setup](#development-setup) below.

### 5. Commit your changes

Write clear, concise commit messages:

```bash
git commit -m "Fix: correct normal vector orientation in Euler angle export"
git commit -m "Feature: add support for MRC output format"
```

### 6. Push and open a Pull Request

```bash
git push origin your-branch-name
```

Then open a Pull Request on GitHub. Fill in the PR template — describe what changed and why.

---

## Development Setup

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

#Conda environment
conda create -n pickme
conda activate pickme

# Install the package in editable mode with dev dependencies
pip install -e '.[dev]'
```

If the project doesn't have a `[dev]` extras group yet, just install the base dependencies:

```bash
pip install -e .
```

> **Note:** If you run into setup issues, please open an issue — it may be a documentation gap worth fixing.

---

## Code Style

We keep things simple:

- Follow [PEP 8](https://peps.python.org/pep-0008/) where reasonable
- Add docstrings to new functions and classes
- Keep functions focused — do one thing well
- Comment non-obvious logic, especially anything mathematically involved

We don't enforce a strict linter on contributors, but clean and readable code is appreciated.

---

## Pull Request Process

1. **Open your PR** against the `main` branch (or `dev` if one exists)
2. **Describe your changes** — what problem does this solve, and how?
3. **Link the related issue** using `Closes #123` in the PR description
4. **A maintainer will review** and may suggest changes or ask questions
5. Once approved, a maintainer will merge your PR

There's no requirement for tests or a changelog entry, though both are appreciated if relevant. Don't let the absence of tests stop you from contributing — we can work through that together.

---

## Questions & Discussions

Not sure where to start? Have a question about the codebase? Feel free to:

- Open a [GitHub Discussion](../../discussions) (if enabled)
- Ask in the relevant issue thread
- Open a plain issue with a `question` label

We're happy to help and want contributing to be a positive experience.

---

*Thank you for helping make this tool better!* 🙏


##Disclaimer**
I am new to this, so please do bear with me if anything is, structurally wrong or if things take a long time - still a work in progress but we will get there!
