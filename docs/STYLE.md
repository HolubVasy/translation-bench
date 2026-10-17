# Code style

Five rules. They are checked in review; a change that breaks one is a
finding. The yardstick is "readable on one screen by someone who did not
write it", not purity.

## 1. One function, one job, one screen

A function does one thing and fits on a screen (about 40 lines). `main()`
only orchestrates: load, call, print, return code. Logic never lives in
`main()`, in a loop body inside `main()`, or in a nested function. When a
function needs a comment to separate its parts, split it at the comment.

## 2. Names say what, types say how

Functions are verbs with the object: `load_cfg`, `build_segments`,
`check_numbers`, `write_manifest`. Data is nouns: `segments`, `judgments`.
Booleans read as questions: `is_furniture`, `has_image`, `passed`.
Allowed short names: `cfg`, `src`, `tr`, `seg`, `err`. Nothing else is
abbreviated. A name that needs a comment to be understood is wrong.

## 3. IO at the edges, logic in the middle

Every stage is a pipeline: `load -> compute -> write`. Loaders and writers
touch files, print nothing and hold no logic. Logic functions take plain
data (dicts, lists) and return plain data; they never read a file, never
print, never call the network. This is what makes them testable offline.
Expected failures (a bad reply, a failed gate) are returned as data: a
list of problems, a record with `passed: False`. Exceptions are for
programmer errors and for a transport that is really down.

## 4. Extend by adding an entry, not a class

A new gate, planter, check or criterion is one function plus one line in a
registry dict (`GATES = {"length": check_length, ...}`). Behaviour that
varies by model or run lives in `config.yaml`. No base classes, interfaces
or plugin loaders until there are three real implementations of the same
shape; two similar functions are cheaper to read than one abstraction.
Dependencies are added only when they replace at least fifty lines.

## 5. Every logic function has a test; every message has a location

A function that computes something has a unit test in `tests/`, offline,
using small literal fixtures. Problems and flags name where they are
(`a1 S2-p3`, `skills/judge.md`, `config.yaml: judges`) so nobody has to
search. Output is ASCII; prose for the owner is in the reply, not in the
code.

## Module layout

Top to bottom: docstring with usage, imports, constants and registries,
loaders, logic, writers, `main()`. A reader meets the vocabulary before the
code that uses it.
