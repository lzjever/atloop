def add(a, b):
    """返回两个数的和"""
    return a + b

def subtract(a, b):
    """返回两个数的差"""
    return a - b

def multiply(a, b):
    """返回两个数的积"""
    return a * b

def divide(a, b):
    """
    返回两个数的商
    如果除数为0，抛出 ValueError 异常
    """
    if b == 0:
        raise ValueError("除数不能为0")
    return a / b
