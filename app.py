#!/usr/bin/env python3
"""逻辑代数化简器 — Flask API 服务"""

import re
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from simplifier import safe_simplify

app = Flask(__name__)
CORS(app)  # 允许跨域请求，防止浏览器拦截


# ---------- 简写格式 → 方括号格式 转换器 ----------

def _shorthand_to_bracket(expr: str) -> str:
    """
    将简写格式转换为方括号格式。
    若表达式已含 '[' 则视为已是方括号格式，直接原样返回。

    简写规则:
      ab   → a[and]b          (变量并列 = AND)
      a+b  → a[or]b           ( + = OR )
      a'   → ([not]a)          (后缀 ' = NOT)
      (x)' → ([not]x)

    优先级（由高到低）: ' → 并列(AND) → +
    """
    if '[' in expr:
        return expr  # 已经是方括号格式

    # ----- 令牌化 -----
    tokens = []
    for c in expr:
        if c in "()+'" or c.isalpha():
            tokens.append(c)
        # 其余字符（空白等）忽略

    # ----- 递归下降解析，直接输出方括号字符串 -----
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
        """var | ( or_expr )"""
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
        """primary (')*"""
        result = parse_primary()
        while peek() == "'":
            consume("'")
            result = f"([not]{result})"
        return result

    def parse_and():
        """not_expr (not_expr)*    (并列 = AND)"""
        left = parse_not()
        while peek() is not None and peek() not in '+)':
            right = parse_not()
            left = f"({left}[and]{right})"
        return left

    def parse_or():
        """and_expr ('+' and_expr)*"""
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
    """
    将方括号格式表达式转换为简写格式。
    仅处理 and/or/not；遇到 [nand]/[nor] 时原样返回。
    """
    # 如果不是标准的 and/or/not 表达式，直接返回（如 NAND/NOR 表达式）
    if any(op in expr for op in ('[nand]', '[nor]', '[xor]', '[xnor]')):
        return expr

    # ----- 令牌化 -----
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
        """var | const | ( not? expr )"""
        tok = peek()
        if tok[0] == 'var':
            consume()
            return ('var', tok[1]), 0           # precedence 0
        if tok[0] == 'const':
            consume()
            return ('const', tok[1]), 0

        consume('(')
        # 判断是否 NOT 表达式
        if peek()[0] == 'op' and peek()[1] == 'not':
            consume('op')      # [not]
            child, child_p = parse_atom()
            consume(')')
            return ('not', child), 1            # precedence 1
        # 否则是二元运算
        left, lp = parse_atom()
        op_tok = consume('op')
        right, rp = parse_atom()
        consume(')')
        prec = {'and': 2, 'or': 3}.get(op_tok[1], 4)
        return (op_tok[1], left, right), prec

    ast, _ = parse_atom()

    # ----- AST → 简写字符串 -----
    def emit(node):
        kind = node[0]
        if kind == 'var':
            return node[1]
        if kind == 'const':
            return node[1]
        if kind == 'not':
            inner = emit(node[1])
            # 子表达式是二元运算才加括号
            if node[1][0] in ('and', 'or'):
                return f"({inner})'"
            return f"{inner}'"
        if kind == 'and':
            left_s = emit(node[1])
            right_s = emit(node[2])

            # 对于 AND，子表达式是 OR 时需要加括号
            if node[1][0] == 'or':
                left_s = f"({left_s})"
            if node[2][0] == 'or':
                right_s = f"({right_s})"
            return f"{left_s}{right_s}"
        if kind == 'or':
            left_s = emit(node[1])
            right_s = emit(node[2])
            return f"{left_s}+{right_s}"
        # 其他（理论上不会走到这里）
        return expr

    return emit(ast)


# ---------- Flask 路由 ----------

@app.route('/')
def index():
    """前端页面"""
    return render_template('index.html')


@app.route('/api/simplify', methods=['POST'])
def api_simplify():
    """化简 API"""
    data = request.get_json(silent=True)
    if not data or 'expression' not in data:
        return jsonify({'success': False, 'error': '请求缺少 expression 字段'})

    raw = data['expression'].strip()
    if not raw:
        return jsonify({'success': False, 'error': '表达式不能为空'})

    # 将简写转换为方括号格式
    try:
        expr = _shorthand_to_bracket(raw)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})

    result = safe_simplify(expr)

    # 将最简式的方括号格式转为简写格式
    if result.get('success') and result.get('simplified'):
        result['simplified_bracket'] = result['simplified']
        result['simplified'] = _bracket_to_shorthand(result['simplified'])

    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
