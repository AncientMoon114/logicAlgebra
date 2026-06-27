"""逻辑代数基本运算模块
提供与、或、非、异或、同或等逻辑运算函数。
"""


def and_op(a: bool, b: bool) -> bool:
    """逻辑与 (AND) — 两个输入同时为真时输出真。"""
    return a and b


def or_op(a: bool, b: bool) -> bool:
    """逻辑或 (OR) — 任一输入为真时输出真。"""
    return a or b


def not_op(a: bool) -> bool:
    """逻辑非 (NOT) — 取反。"""
    return not a


def xor_op(a: bool, b: bool) -> bool:
    """异或 (XOR) — 两个输入不同时输出真。"""
    return a != b


def xnor_op(a: bool, b: bool) -> bool:
    """同或 (XNOR) — 两个输入相同时输出真。"""
    return a == b
