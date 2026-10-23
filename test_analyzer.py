import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyzer import analyze, lex, Parser, CompileError

class AnalyzerTests(unittest.TestCase):
    def test_token_positions_and_comments(self):
        ts=lex("int x; // c\nprint(x);")
        self.assertEqual([(t.kind,t.line) for t in ts[:3]],[('INT',1),('IDENT',1),('OP',1)])
        self.assertEqual(ts[-2].line,2)
    def test_precedence_and_ast(self):
        result=analyze("int x; x = 2 + 3 * 4;")
        self.assertEqual(result['ast']['children'][1]['children'][0]['value'],'+')
        self.assertEqual(result['optimized'],"int x;\nx = 14;")
    def test_undeclared_and_duplicate(self):
        codes={d['code'] for d in analyze("x = 1; int y; int y; print(z);")['diagnostics']}
        self.assertIn('E001',codes); self.assertIn('E002',codes); self.assertIn('W001',codes)
    def test_redundant_arithmetic(self):
        self.assertIn('x = 5;',analyze("int x; x = 5 + 0;")['optimized'])
        self.assertIn('O001',[d['code'] for d in analyze("int x; x = 2 * 3;")['diagnostics']])
    def test_constant_branches(self):
        result=analyze("int x; if (0) { x = 1; } else { x = 2; } print(x);")
        self.assertIn('always false',[d['message'] for d in result['diagnostics']][0])
        self.assertIn('x = 2;',result['optimized']); self.assertNotIn('x = 1;',result['optimized'])
    def test_lexer_and_parser_errors_have_locations(self):
        for code in ("int x; @", "int x x;"):
            with self.assertRaises(CompileError) as cm: analyze(code)
            self.assertGreaterEqual(cm.exception.column,1)
    def test_division_by_zero_is_not_folded(self):
        result=analyze("int x; x = 8 / 0;")
        self.assertIn('8 / 0',result['optimized'])
    def test_loop_assignment_does_not_escape_as_constant(self):
        result=analyze("int x; x = 1; while (x > 0) { x = x - 1; } print(x);")
        self.assertIn('print(x);',result['optimized'])

if __name__=='__main__': unittest.main()
