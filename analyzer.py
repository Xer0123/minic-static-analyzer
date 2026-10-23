"""Compiler-based static analyzer for the MiniC teaching language."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Token:
    kind: str
    value: str
    line: int
    column: int


class CompileError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.message, self.line, self.column = message, line, column


def lex(source: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, col = 0, 1, 1
    two = {"==", "!=", "<=", ">="}
    singles = set("+-*/%=;(){}<>")
    while i < len(source):
        c = source[i]
        if c.isspace():
            if c == "\n": line, col = line + 1, 1
            else: col += 1
            i += 1; continue
        if source.startswith("//", i):
            while i < len(source) and source[i] != "\n": i += 1; col += 1
            continue
        start, start_col = i, col
        if c.isalpha() or c == "_":
            i += 1; col += 1
            while i < len(source) and (source[i].isalnum() or source[i] == "_"): i += 1; col += 1
            value = source[start:i]
            tokens.append(Token(value.upper() if value in {"int", "if", "else", "while", "print"} else "IDENT", value, line, start_col)); continue
        if c.isdigit():
            i += 1; col += 1
            while i < len(source) and source[i].isdigit(): i += 1; col += 1
            tokens.append(Token("NUMBER", source[start:i], line, start_col)); continue
        if source[i:i+2] in two:
            tokens.append(Token("OP", source[i:i+2], line, col)); i += 2; col += 2; continue
        if c in singles:
            tokens.append(Token("OP", c, line, col)); i += 1; col += 1; continue
        raise CompileError(f"Unexpected character {c!r}", line, col)
    tokens.append(Token("EOF", "", line, col))
    return tokens


@dataclass
class Node:
    kind: str
    line: int
    column: int
    value: Any = None
    children: list[Node] = field(default_factory=list)


class Parser:
    PRECEDENCE = {"==": 1, "!=": 1, "<": 1, "<=": 1, ">": 1, ">=": 1, "+": 2, "-": 2, "*": 3, "/": 3, "%": 3}
    def __init__(self, tokens: list[Token]): self.tokens, self.i = tokens, 0
    @property
    def t(self): return self.tokens[self.i]
    def take(self): t = self.t; self.i += 1; return t
    def expect(self, value: str):
        if self.t.value != value: raise CompileError(f"Expected {value!r}, found {self.t.value or 'end of input'!r}", self.t.line, self.t.column)
        return self.take()
    def parse(self):
        statements = []
        while self.t.kind != "EOF": statements.append(self.statement())
        return Node("program", 1, 1, children=statements)
    def statement(self):
        t = self.t
        if t.kind == "INT":
            self.take(); name = self.expect_ident(); self.expect(";"); return Node("decl", t.line, t.column, name.value)
        if t.kind == "IDENT":
            name = self.take(); self.expect("="); expr = self.expression(); self.expect(";"); return Node("assign", name.line, name.column, name.value, [expr])
        if t.kind == "PRINT":
            self.take(); self.expect("("); expr = self.expression(); self.expect(")"); self.expect(";"); return Node("print", t.line, t.column, children=[expr])
        if t.kind in ("IF", "WHILE"):
            self.take(); kind = t.value; self.expect("("); cond = self.expression(); self.expect(")"); body = self.block()
            other = self.block() if kind == "if" and self.t.kind == "ELSE" and self.take() else None
            return Node(kind, t.line, t.column, children=[cond, body] + ([other] if other else []))
        if t.value == "{": return self.block()
        raise CompileError(f"Expected a statement, found {t.value or 'end of input'!r}", t.line, t.column)
    def block(self):
        t = self.expect("{"); children=[]
        while self.t.value != "}":
            if self.t.kind == "EOF": raise CompileError("Unclosed block", t.line, t.column)
            children.append(self.statement())
        self.take(); return Node("block", t.line, t.column, children=children)
    def expect_ident(self):
        if self.t.kind != "IDENT": raise CompileError("Expected a variable name", self.t.line, self.t.column)
        return self.take()
    def expression(self, min_prec=1):
        t=self.take()
        if t.kind == "NUMBER": left=Node("number",t.line,t.column,int(t.value))
        elif t.kind == "IDENT": left=Node("var",t.line,t.column,t.value)
        elif t.value in ("-", "+"):
            left=Node("unary",t.line,t.column,t.value,[self.expression(4)])
        elif t.value == "(":
            left=self.expression(); self.expect(")")
        else: raise CompileError(f"Expected an expression, found {t.value or 'end of input'!r}",t.line,t.column)
        while self.t.value in self.PRECEDENCE and self.PRECEDENCE[self.t.value]>=min_prec:
            op=self.take(); right=self.expression(self.PRECEDENCE[op.value]+1); left=Node("binary",op.line,op.column,op.value,[left,right])
        return left


def literal(node: Node) -> int | None:
    if node.kind == "number": return node.value
    if node.kind == "unary":
        x=literal(node.children[0]); return None if x is None else (x if node.value=="+" else -x)
    if node.kind == "binary":
        a,b=map(literal,node.children)
        if a is None or b is None: return None
        try:
            def trunc_div(x,y): return (abs(x)//abs(y)) * (-1 if (x<0) != (y<0) else 1)
            return {"+":lambda:a+b,"-":lambda:a-b,"*":lambda:a*b,"/":lambda:trunc_div(a,b),"%":lambda:a-trunc_div(a,b)*b,"==":lambda:int(a==b),"!=":lambda:int(a!=b),"<":lambda:int(a<b),"<=":lambda:int(a<=b),">":lambda:int(a>b),">=":lambda:int(a>=b)}[node.value]()
        except (ZeroDivisionError, OverflowError): return None
    return None


def render_expr(n: Node) -> str:
    if n.kind in ("number", "var"): return str(n.value)
    if n.kind == "unary": return f"{n.value}{render_expr(n.children[0])}"
    return f"{render_expr(n.children[0])} {n.value} {render_expr(n.children[1])}"


def render_program(program: Node) -> str:
    lines=[]
    def emit(n, depth=0):
        pad="    "*depth
        if n.kind=="program" or n.kind=="block":
            for c in n.children: emit(c,depth)
        elif n.kind=="decl": lines.append(pad+f"int {n.value};")
        elif n.kind=="assign": lines.append(pad+f"{n.value} = {render_expr(n.children[0])};")
        elif n.kind=="print": lines.append(pad+f"print({render_expr(n.children[0])});")
        elif n.kind in ("if","while"):
            lines.append(pad+f"{n.kind} ({render_expr(n.children[0])}) {{"); emit(n.children[1],depth+1); lines.append(pad+"}")
            if n.kind=="if" and len(n.children)>2: lines.append(pad+"else {"); emit(n.children[2],depth+1); lines.append(pad+"}")
    emit(program); return "\n".join(lines)


def analyze(source: str) -> dict:
    tokens=lex(source); ast=Parser(tokens).parse(); diagnostics=[]; declared={}; used=set(); assigned=set()
    def diag(severity,code,msg,line,col,fix=None): diagnostics.append({"severity":severity,"code":code,"message":msg,"line":line,"column":col,"recommendation":fix})
    def check_expr(n):
        if n.kind=="var":
            if n.value not in declared: diag("error","E001",f"Variable '{n.value}' is used before it is declared.",n.line,n.column,"Declare it with int before use.")
            else: used.add(n.value)
        for c in n.children: check_expr(c)
    def walk(n, reachable=True):
        if n.kind in ("program","block"):
            for c in n.children: walk(c,reachable)
        elif n.kind=="decl":
            if n.value in declared: diag("error","E002",f"Variable '{n.value}' is declared more than once.",n.line,n.column,"Keep one declaration for this variable.")
            else: declared[n.value]=n
        elif n.kind=="assign":
            check_expr(n.children[0]); assigned.add(n.value)
            if n.value not in declared: diag("error","E001",f"Variable '{n.value}' is assigned before it is declared.",n.line,n.column,"Declare it with int before assignment.")
        elif n.kind=="print": check_expr(n.children[0])
        elif n.kind in ("if","while"):
            check_expr(n.children[0]); value=literal(n.children[0])
            if value is not None:
                if n.kind=="if" and value==0:
                    diag("warning","W003","Condition is always false; the if body is unreachable.",n.line,n.column,"Remove the unreachable branch or correct the condition.")
                    if len(n.children)>2: walk(n.children[2],reachable)
                    return
                if n.kind=="if" and value!=0:
                    diag("warning","W003","Condition is always true; the else branch is unreachable.",n.line,n.column,"Remove the unreachable branch or correct the condition.")
                    walk(n.children[1],reachable); return
                if n.kind=="while" and value==0:
                    diag("warning","W003","Loop condition is always false; the loop body is unreachable.",n.line,n.column,"Remove the unreachable loop or correct the condition."); return
            walk(n.children[1],reachable)
            if len(n.children)>2: walk(n.children[2],reachable)
    walk(ast)
    for name,node in declared.items():
        if name not in used: diag("warning","W001",f"Variable '{name}' is declared but never read.",node.line,node.column,"Remove the declaration or use the variable.")
    optimized, opt_messages = optimize(ast)
    diagnostics.extend(opt_messages)
    return {"tokens":[{"kind":t.kind,"value":t.value,"line":t.line,"column":t.column} for t in tokens if t.kind!="EOF"],"ast":ast_json(ast),"diagnostics":sorted(diagnostics,key=lambda d:(d["line"],d["column"],d["severity"])),"optimized":render_program(optimized),"original":source.rstrip()}


def ast_json(n): return {"kind":n.kind,"value":n.value,"line":n.line,"column":n.column,"children":[ast_json(c) for c in n.children]}


def optimize(ast: Node):
    import copy
    out=copy.deepcopy(ast); messages=[]; constants={}
    def assigned_names(n):
        found=set()
        if n.kind=="assign": found.add(n.value)
        for child in n.children: found.update(assigned_names(child))
        return found
    def expr(n):
        if n.kind=="var" and n.value in constants and constants[n.value] is not None: return Node("number",n.line,n.column,constants[n.value])
        n.children=[expr(c) for c in n.children]
        if n.kind=="binary":
            a,b=n.children; av,bv=literal(a),literal(b)
            if av is not None and bv is not None:
                result=literal(n)
                if result is not None:
                    messages.append({"severity":"hint","code":"O001","message":f"Constant expression {render_expr(n)} can be folded to {result}.","line":n.line,"column":n.column,"recommendation":"Use the computed constant."})
                    return Node("number",n.line,n.column,result)
            if n.value=="+" and bv==0: return a
            if n.value=="+" and av==0: return b
            if n.value=="-" and bv==0: return a
            if n.value=="*" and bv==1: return a
            if n.value=="*" and av==1: return b
            if n.value=="*" and (av==0 or bv==0): return Node("number",n.line,n.column,0)
            if n.value=="/" and bv==1: return a
        if n.kind=="unary" and literal(n) is not None: return Node("number",n.line,n.column,literal(n))
        return n
    def block(n):
        nonlocal constants
        kept=[]
        for s in n.children:
            if s.kind=="decl": kept.append(s); constants.pop(s.value,None)
            elif s.kind=="assign":
                s.children[0]=expr(s.children[0]); val=literal(s.children[0]); constants[s.value]=val if val is not None else None; kept.append(s)
            elif s.kind=="print": s.children[0]=expr(s.children[0]); kept.append(s)
            elif s.kind in ("if","while"):
                before=constants.copy()
                mutated=assigned_names(s.children[1]) if s.kind=="while" else set()
                if s.kind=="while":
                    for name in mutated: constants[name]=None
                s.children[0]=expr(s.children[0]); val=literal(s.children[0])
                if s.kind=="if" and val is not None:
                    chosen=s.children[1] if val else (s.children[2] if len(s.children)>2 else None)
                    if chosen:
                        constants=before.copy(); block(chosen); kept.extend(chosen.children); constants=before
                    continue
                if s.kind=="while" and val==0: continue
                if s.kind=="while":
                    constants=before.copy()
                    for name in mutated: constants[name]=None
                    block(s.children[1])
                    constants=before.copy()
                    for name in mutated: constants[name]=None
                    kept.append(s)
                    continue
                constants=before.copy(); block(s.children[1]); then_consts=constants.copy()
                if len(s.children)>2:
                    constants=before.copy(); block(s.children[2]); else_consts=constants.copy()
                    constants={k:v for k,v in then_consts.items() if else_consts.get(k)==v}
                else: constants={k:None for k in set(before)|set(then_consts)}
                kept.append(s)
            else: kept.append(s)
        n.children=kept
    block(out)
    return out,messages
