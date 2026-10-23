# MiniC Static Analyzer and Optimization Advisor

A small educational compiler pipeline for a restricted C-like language. It includes a handwritten lexer, recursive-descent / precedence parser, JSON AST, symbol-table checks, explainable diagnostics, and conservative constant folding / propagation. A browser interface runs locally with Python's standard library; source code is not sent to a service.

## Run

Requires Python 3.10 or newer. No third-party packages are needed.

```powershell
python app.py
```

Open `http://127.0.0.1:8000`. Use `python app.py --no-browser` to start without opening a tab. `python -m unittest discover -s tests -v` runs the included checks.

## MiniC syntax

```text
program    := statement*
statement  := "int" IDENT ";"
           | IDENT "=" expression ";"
           | "print" "(" expression ")" ";"
           | "if" "(" expression ")" block ("else" block)?
           | "while" "(" expression ")" block
block      := "{" statement* "}"
expression := integers, identifiers, unary +/- and binary + - * / %
              with comparisons == != < <= > >=
```

`//` starts a line comment. Variables share one flat scope. The analyzer reports undeclared names, repeated declarations, unread declarations, constant-condition branches and safe simplification opportunities. It does not execute the program. It is not a C compiler and does not claim exhaustive data-flow analysis.

## Architecture

`app.py` serves the browser UI and `/api/analyze`; `analyzer.py` contains the lexer, parser, AST, semantic analysis, optimizer and code renderer. The pipeline is source → tokens → AST → semantic checks → optimization suggestions → report.

## Tests and limits

The test suite covers token locations, precedence and AST shape, syntax/lexical errors, semantic diagnostics, constant folding, branch handling and safe arithmetic cases. Constant propagation is intentionally local and conservative; values crossing dynamic control-flow joins are not assumed to remain constant.
