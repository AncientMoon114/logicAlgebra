#!/usr/bin/env python3
"""逻辑代数化简器 — Flask API 服务"""

import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from simplifier import safe_simplify

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = str(BASE_DIR / 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)
CORS(app)


# ---------- 简写格式 → 方括号格式 转换器 ----------

def _shorthand_to_bracket(expr: str) -> str:
    """将简写格式转换为方括号格式。若已含 '[' 则直接原样返回。

    简写规则:
      ab   → a[and]b     (变量并列 = AND)
      a+b  → a[or]b      (+ = OR)
      a'   → ([not]a)    (后缀 ' = NOT)
      (x)' → ([not]x)

    优先级: ' → 并列(AND) → +
    """
    if '[' in expr:
        return expr

    tokens = [c for c in expr if c in "()+'" or c.isalpha()]
    pos = 0
    n = len(tokens)

    def peek():
        return tokens[pos] if pos < n else None

    def consume(expected=None):
        nonlocal pos
        tok = peek()
        if tok is None:
            raise ValueError("表达式不完整")
        if expected is not None and tok != expected:
            raise ValueError(f"期望 '{expected}'，得到 '{tok}'")
        pos += 1
        return tok

    def parse_primary():
        tok = peek()
        if tok is None:
            raise ValueError("表达式不完整")
        if tok.isalpha():
            consume()
            return tok
        if tok == '(':
            consume('(')
            inner = parse_or()
            consume(')')
            return inner
        raise ValueError(f"意外的符号: {tok}")

    def parse_not():
        result = parse_primary()
        while peek() == "'":
            consume("'")
            result = f"([not]{result})"
        return result

    def parse_and():
        left = parse_not()
        while peek() is not None and peek() not in '+)':
            right = parse_not()
            left = f"({left}[and]{right})"
        return left

    def parse_or():
        left = parse_and()
        while peek() == '+':
            consume('+')
            right = parse_and()
            left = f"({left}[or]{right})"
        return left

    result = parse_or()
    if pos < n:
        raise ValueError(f"意外的符号: {tokens[pos]}")
    return result


# ---------- 方括号格式 → 简写格式 转换器 ----------

def _bracket_to_shorthand(expr: str) -> str:
    """将方括号格式转换为简写格式。遇到 [nand]/[nor] 时原样返回。"""
    if any(op in expr for op in ('[nand]', '[nor]', '[xor]', '[xnor]')):
        return expr

    tokens = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c == '(':
            tokens.append(('(',))
            i += 1
        elif c == ')':
            tokens.append((')',))
            i += 1
        elif c == '[':
            j = expr.index(']', i)
            tokens.append(('op', expr[i + 1:j]))
            i = j + 1
        elif c.isalpha():
            tokens.append(('var', c))
            i += 1
        elif c in '01':
            tokens.append(('const', c))
            i += 1
        else:
            i += 1

    if not tokens:
        return expr

    pos = 0
    n = len(tokens)

    def peek():
        return tokens[pos] if pos < n else None

    def consume(t=None):
        nonlocal pos
        tok = peek()
        if tok is None:
            raise ValueError("表达式不完整")
        if t is not None and tok[0] != t:
            raise ValueError(f"期望 {t}，得到 {tok}")
        pos += 1
        return tok

    def parse_atom():
        tok = peek()
        if tok[0] == 'var':
            consume()
            return ('var', tok[1]), 0
        if tok[0] == 'const':
            consume()
            return ('const', tok[1]), 0
        consume('(')
        if peek()[0] == 'op' and peek()[1] == 'not':
            consume('op')
            child, child_p = parse_atom()
            consume(')')
            return ('not', child), 1
        left, lp = parse_atom()
        op_tok = consume('op')
        right, rp = parse_atom()
        consume(')')
        return (op_tok[1], left, right), {'and': 2, 'or': 3}.get(op_tok[1], 4)

    ast, _ = parse_atom()

    def emit(node):
        kind = node[0]
        if kind == 'var':
            return node[1]
        if kind == 'const':
            return node[1]
        if kind == 'not':
            inner = emit(node[1])
            return f"({inner})'" if node[1][0] in ('and', 'or') else f"{inner}'"
        if kind == 'and':
            left_s = emit(node[1])
            right_s = emit(node[2])
            if node[1][0] == 'or':
                left_s = f"({left_s})"
            if node[2][0] == 'or':
                right_s = f"({right_s})"
            return f"{left_s}{right_s}"
        if kind == 'or':
            return f"{emit(node[1])}+{emit(node[2])}"
        return expr

    return emit(ast)


# ---------- Flask 路由 ----------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/simplify', methods=['POST'])
def api_simplify():
    data = request.get_json(silent=True)
    if not data or 'expression' not in data:
        return jsonify({'success': False, 'error': '请求缺少 expression 字段'})

    raw = data['expression'].strip()
    if not raw:
        return jsonify({'success': False, 'error': '表达式不能为空'})

    try:
        expr = _shorthand_to_bracket(raw)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})

    result = safe_simplify(expr)

    if result.get('success') and result.get('simplified'):
        result['simplified_bracket'] = result['simplified']
        result['simplified'] = _bracket_to_shorthand(result['simplified'])

    return jsonify(result)


def auto_open_browser() -> None:
    """启动后自动打开默认浏览器，跳转到本地 UI 页面。"""
    url = 'http://127.0.0.1:8080/'

    def _open() -> None:
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            pass

    threading.Timer(1.0, _open).start()


if __name__ == '__main__':
    auto_open_browser()
    app.run(host='0.0.0.0', port=8080, debug=False)
