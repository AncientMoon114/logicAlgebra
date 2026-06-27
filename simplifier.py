"""
逻辑表达式化简模块

接收字符串形式的逻辑表达式（如 "(a[or]b)[and]([not]c)"），
返回最简表达式、最简与非表达式和最简或非表达式。
"""

from itertools import product
from logic_gates import and_op, or_op, not_op, xor_op, xnor_op


# ===========================================================
#  1. 令牌化 (Tokenizer)
# ===========================================================

def tokenize(expr: str):
    """将表达式字符串拆分为令牌流。"""
    tokens = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c == '(':
            tokens.append(('(', '('))
            i += 1
        elif c == ')':
            tokens.append((')', ')'))
            i += 1
        elif c == '[':
            j = expr.index(']', i)
            op = expr[i + 1:j]
            if op not in ('and', 'or', 'not', 'xor', 'xnor'):
                raise ValueError(f"未知运算符: [{op}]")
            tokens.append(('op', op))
            i = j + 1
        elif c.isalpha():
            tokens.append(('var', c))
            i += 1
        else:
            i += 1  # 跳过空白
    return tokens


# ===========================================================
#  2. 抽象语法树 (AST)
# ===========================================================

class Node:
    """AST 节点。"""
    def __init__(self, kind, value=None, left=None, right=None):
        self.kind = kind   # 'var' | 'const' | 'not' | 'and' | 'or' | 'xor' | 'xnor'
        self.value = value # 变量名或 '0'/'1'
        self.left = left
        self.right = right

    # ----- 字符串输出（与输入格式保持一致） -----

    def to_str(self):
        if self.kind == 'var':
            return self.value
        if self.kind == 'const':
            return self.value
        if self.kind == 'not':
            inner = self.left.to_str()
            # 不是简单变量才加括号
            if self.left.kind in ('and', 'or', 'not'):
                return f"([not]{inner})"
            return f"([not]{inner})"
        # 二元运算符
        op_map = {'and': 'and', 'or': 'or',
                  'nand': 'nand', 'nor': 'nor'}
        op = op_map.get(self.kind, self.kind)
        return f"({self.left.to_str()}[{op}]{self.right.to_str()})"

    def copy(self):
        if self.kind in ('var', 'const'):
            return Node(self.kind, value=self.value)
        if self.kind == 'not':
            return Node('not', left=self.left.copy())
        return Node(self.kind, left=self.left.copy(), right=self.right.copy())


# ===========================================================
#  3. 递归下降解析器
# ===========================================================

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected=None):
        tok = self.peek()
        if tok is None:
            raise ValueError("表达式不完整")
        if expected and tok[0] != expected:
            raise ValueError(f"期望 {expected}，得到 {tok[0]} ({tok})")
        self.pos += 1
        return tok

    def parse(self):
        """解析完整表达式。"""
        result = self.parse_or()
        if self.peek() is not None:
            raise ValueError(f"意外的令牌: {self.peek()}")
        return result

    def parse_or(self):
        """处理 OR 层: xor_expr ([or] xor_expr)*"""
        left = self.parse_xor()
        while self.peek() and self.peek()[0] == 'op' and self.peek()[1] == 'or':
            self.consume()
            right = self.parse_xor()
            left = Node('or', left=left, right=right)
        return left

    def parse_xor(self):
        """处理 XOR/XNOR 层: and_expr ([xor] and_expr | [xnor] and_expr)*"""
        left = self.parse_and()
        while self.peek() and self.peek()[0] == 'op' and self.peek()[1] in ('xor', 'xnor'):
            op = self.consume()[1]
            right = self.parse_and()
            left = Node(op, left=left, right=right)
        return left

    def parse_and(self):
        """处理 AND 层: not_expr ([and] not_expr)*"""
        left = self.parse_not()
        while self.peek() and self.peek()[0] == 'op' and self.peek()[1] == 'and':
            self.consume()
            right = self.parse_not()
            left = Node('and', left=left, right=right)
        return left

    def parse_not(self):
        """处理 NOT 层: [not]* primary"""
        cnt = 0
        while self.peek() and self.peek()[0] == 'op' and self.peek()[1] == 'not':
            self.consume()
            cnt += 1
        child = self.parse_primary()
        # 多个 NOT 叠用取模
        for _ in range(cnt % 2):
            child = Node('not', left=child)
        return child

    def parse_primary(self):
        """基本元素: var | ( expr )"""
        tok = self.peek()
        if tok is None:
            raise ValueError("表达式不完整")
        if tok[0] == 'var':
            self.consume()
            return Node('var', value=tok[1])
        if tok[0] == '(':
            self.consume()
            expr = self.parse_or()
            if self.peek() is None or self.peek()[0] != ')':
                raise ValueError("缺少右括号 )")
            self.consume()
            return expr
        raise ValueError(f"意外的令牌: {tok}")


# ===========================================================
#  4. 真值表生成
# ===========================================================

def _collect_vars(node):
    """递归收集所有变量名。"""
    s = set()
    def walk(n):
        if n.kind == 'var':
            s.add(n.value)
        elif n.kind == 'not':
            walk(n.left)
        elif n.kind in ('and', 'or', 'xor', 'xnor'):
            walk(n.left)
            walk(n.right)
    walk(node)
    return sorted(s)


def _eval_node(node, assignment):
    """在给定变量赋值下求值。"""
    if node.kind == 'var':
        return bool(assignment[node.value])
    if node.kind == 'const':
        return node.value == '1'
    if node.kind == 'not':
        return not_op(_eval_node(node.left, assignment))
    if node.kind == 'and':
        return and_op(_eval_node(node.left, assignment),
                      _eval_node(node.right, assignment))
    if node.kind == 'or':
        return or_op(_eval_node(node.left, assignment),
                     _eval_node(node.right, assignment))
    if node.kind == 'xor':
        return xor_op(_eval_node(node.left, assignment),
                      _eval_node(node.right, assignment))
    if node.kind == 'xnor':
        return xnor_op(_eval_node(node.left, assignment),
                       _eval_node(node.right, assignment))
    raise ValueError(f"未知节点类型: {node.kind}")


def build_truth_table(node):
    """
    构建真值表。
    返回 (变量列表, 最小项索引集合)。
    索引按变量列表顺序编码：bit i = vars[i] 的值。
    """
    vars_list = _collect_vars(node)
    n = len(vars_list)
    minterms = set()

    for bits in product((False, True), repeat=n):
        assignment = dict(zip(vars_list, bits))
        if _eval_node(node, assignment):
            idx = 0
            for i, v in enumerate(bits):
                if v:
                    idx |= (1 << i)
            minterms.add(idx)

    return vars_list, minterms


# ===========================================================
#  5. Quine-McCluskey 最小化
# ===========================================================

def _count_ones(x):
    return x.bit_count()


def _find_prime_implicants(minterms, n_vars):
    """
    找出所有质蕴含项。
    返回: list of (bits, dc_mask, covered_mintems_set)
    """
    # 初始项：每个最小项自身
    terms = {(m, 0) for m in minterms}
    prime_implicants = []

    while terms:
        # 按 bits 中 1 的个数分组
        groups = {}
        for bits, dc in terms:
            k = _count_ones(bits)
            groups.setdefault(k, []).append((bits, dc))

        used = set()
        next_terms = set()

        for k in sorted(groups):
            if k + 1 not in groups:
                continue
            for b1, d1 in groups[k]:
                for b2, d2 in groups[k + 1]:
                    if d1 != d2:
                        continue
                    diff = b1 ^ b2
                    if diff == 0 or (diff & (diff - 1)) != 0:
                        continue
                    if diff & d1:
                        continue   # 不同位已在无关项中
                    new_bits = b1 & b2
                    new_dc   = d1 | diff
                    next_terms.add((new_bits, new_dc))
                    used.add((b1, d1))
                    used.add((b2, d2))

        for term in terms:
            if term not in used:
                prime_implicants.append(term)

        terms = next_terms

    # 计算每个质蕴含项覆盖的最小项
    result = []
    all_dc = (1 << n_vars) - 1
    for bits, dc in prime_implicants:
        # 特殊处理：全无关 (恒真)
        if dc == all_dc:
            result.append((bits, dc, set(minterms)))
            continue
        cover = set()
        for m in minterms:
            if (m & ~dc) == bits:
                cover.add(m)
        result.append((bits, dc, cover))

    return result


def _minimal_cover(prime_implicants, minterms):
    """
    用贪心 + 必要项策略选取覆盖全部最小项的最少质蕴含项。
    返回: list of (bits, dc_mask)
    """
    if not minterms:
        return []

    n_pi = len(prime_implicants)
    uncovered = set(minterms)

    # 1. 必要质蕴含项
    essential = set()
    for mt in minterms:
        covering = [i for i in range(n_pi) if mt in prime_implicants[i][2]]
        if len(covering) == 1:
            essential.add(covering[0])

    for i in essential:
        uncovered -= prime_implicants[i][2]

    # 2. 贪心选剩余的
    selected = set(essential)
    remaining = [i for i in range(n_pi) if i not in essential]

    while uncovered and remaining:
        best_i = -1
        best_cov = set()
        for i in remaining:
            cov = prime_implicants[i][2] & uncovered
            if len(cov) > len(best_cov):
                best_cov = cov
                best_i = i
        if best_i == -1:
            break
        selected.add(best_i)
        remaining.remove(best_i)
        uncovered -= best_cov

    return [(prime_implicants[i][0], prime_implicants[i][1]) for i in selected]


# ===========================================================
#  6. 表达式字符串构建
# ===========================================================

def _implicant_to_expr(bits, dc, vars_list):
    """将一个质蕴含项转为 AND 表达式字符串。"""
    literals = []
    for i, var in enumerate(vars_list):
        if dc & (1 << i):
            continue
        if bits & (1 << i):
            literals.append(var)
        else:
            literals.append(f"([not]{var})")
    if not literals:
        return "1"
    expr = literals[0]
    for lit in literals[1:]:
        expr = f"({expr}[and]{lit})"
    return expr


def _sop_to_expr(implicants, vars_list):
    """将质蕴含项列表转为 SOP 表达式字符串。"""
    if not implicants:
        return "0"

    terms = []
    for bits, dc in implicants:
        t = _implicant_to_expr(bits, dc, vars_list)
        if t == "1":
            return "1"   # 只要有一项恒真，整个 SOP 恒真
        terms.append(t)

    expr = terms[0]
    for t in terms[1:]:
        expr = f"({expr}[or]{t})"
    return expr


# ===========================================================
#  7. NAND / NOR 递归转换
# ===========================================================

def _to_nand_ast(node):
    """
    将 AST 递归转为仅含 NAND 的 AST。
    等价关系：
      NOT a   = a NAND a
      a AND b = (a NAND b) NAND (a NAND b)
      a OR b  = (a NAND a) NAND (b NAND b)
    """
    if node.kind in ('var', 'const'):
        return node.copy()
    if node.kind == 'not':
        child = _to_nand_ast(node.left)
        return Node('nand', left=child, right=child)
    if node.kind == 'and':
        left = _to_nand_ast(node.left)
        right = _to_nand_ast(node.right)
        inner = Node('nand', left=left, right=right)
        return Node('nand', left=inner, right=inner)
    if node.kind == 'or':
        left = _to_nand_ast(node.left)
        right = _to_nand_ast(node.right)
        ln = Node('nand', left=left, right=left)
        rn = Node('nand', left=right, right=right)
        return Node('nand', left=ln, right=rn)
    raise ValueError(f"NAND 转换: 未知节点 {node.kind}")


def _to_nor_ast(node):
    """
    将 AST 递归转为仅含 NOR 的 AST。
    等价关系：
      NOT a   = a NOR a
      a OR b  = (a NOR b) NOR (a NOR b)
      a AND b = (a NOR a) NOR (b NOR b)
    """
    if node.kind in ('var', 'const'):
        return node.copy()
    if node.kind == 'not':
        child = _to_nor_ast(node.left)
        return Node('nor', left=child, right=child)
    if node.kind == 'or':
        left = _to_nor_ast(node.left)
        right = _to_nor_ast(node.right)
        inner = Node('nor', left=left, right=right)
        return Node('nor', left=inner, right=inner)
    if node.kind == 'and':
        left = _to_nor_ast(node.left)
        right = _to_nor_ast(node.right)
        ln = Node('nor', left=left, right=left)
        rn = Node('nor', left=right, right=right)
        return Node('nor', left=ln, right=rn)
    raise ValueError(f"NOR 转换: 未知节点 {node.kind}")


# ===========================================================
#  8. 主 API
# ===========================================================

def simplify(expr_str: str):
    """
    化简逻辑表达式，返回三个字符串。

    参数
    ----
    expr_str : str
        形如 "(a[or]b)[and]([not]c)" 的表达式。

    返回
    ----
    (str, str, str)
        (最简表达式, 最简与非表达式, 最简或非表达式)
    """

    # ---- 8a. 解析 ----
    tokens = tokenize(expr_str)
    parser = Parser(tokens)
    ast = parser.parse()

    # ---- 8b. 真值表 ----
    vars_list, minterms = build_truth_table(ast)
    n_vars = len(vars_list)

    # ---- 8c. 特殊常量 ----
    all_minterms = set(range(1 << n_vars)) if n_vars > 0 else set()

    # 恒假
    if not minterms:
        return "0", "0", "0"

    # 恒真
    if minterms == all_minterms:
        const_node = Node('const', value='1')
        nand_str = _to_nand_ast(const_node).to_str()
        nor_str  = _to_nor_ast(const_node).to_str()
        return "1", nand_str, nor_str

    # ---- 8d. QM 最小化得到最简 SOP ----
    pis = _find_prime_implicants(minterms, n_vars)
    minimal = _minimal_cover(pis, minterms)
    simplified = _sop_to_expr(minimal, vars_list)

    # ---- 8e. 解析最简式并递归转 NAND / NOR ----
    simp_tokens = tokenize(simplified)
    simp_ast = Parser(simp_tokens).parse()

    nand_ast = _to_nand_ast(simp_ast)
    nor_ast  = _to_nor_ast(simp_ast)

    nand_str = nand_ast.to_str()
    nor_str  = nor_ast.to_str()

    return simplified, nand_str, nor_str


# ===========================================================
#  9. 安全包装（供 Flask API 调用）
# ===========================================================

def safe_simplify(expr_str: str):
    """
    安全化简，异常时返回错误字典。

    返回
    ----
    dict
        ``{'success': True/False, 'simplified': str, 'nand': str, 'nor': str, 'error': str|None}``
    """
    try:
        s, nand, nor = simplify(expr_str)
        return {
            'success': True,
            'simplified': s,
            'nand': nand,
            'nor': nor,
            'error': None,
        }
    except Exception as e:
        return {
            'success': False,
            'simplified': None,
            'nand': None,
            'nor': None,
            'error': str(e),
        }


# ===========================================================
#  10. 简易测试
# ===========================================================

if __name__ == '__main__':
    test_cases = [
        # (描述, 表达式)
        ("简单 OR",  "a[or]b"),
        ("简单 AND", "a[and]b[and]c"),
        ("带 NOT",   "([not]a)[or]b"),
        ("混合 1",   "(a[or]b)[and]([not]c)"),
        ("异或",     "(a[and]([not]b))[or](([not]a)[and]b)"),
        ("同或",     "(a[and]b)[or](([not]a)[and]([not]b))"),
        ("三项",     "(([not]a)[and]b)[or](a[and]([not]b))[or](a[and]b)"),
        ("嵌套",     "([not](a[and]b))[or](c[and]d)"),
        ("恒真",     "a[or]([not]a)"),
        ("恒假",     "a[and]([not]a)"),
    ]

    for desc, expr in test_cases:
        try:
            s, nand, nor = simplify(expr)
            print(f"[{desc}]")
            print(f"  输入: {expr}")
            print(f"  最简: {s}")
            print(f"  与非: {nand}")
            print(f"  或非: {nor}")
            print()
        except Exception as e:
            print(f"[{desc}] ERROR: {e}")
            print()
