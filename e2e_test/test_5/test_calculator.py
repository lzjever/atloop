import pytest
from calculator import add, subtract, multiply, divide

def test_add():
    """测试加法函数"""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
    assert add(2.5, 3.5) == 6.0

def test_subtract():
    """测试减法函数"""
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5
    assert subtract(10, 10) == 0
    assert subtract(3.5, 1.5) == 2.0

def test_multiply():
    """测试乘法函数"""
    assert multiply(2, 3) == 6
    assert multiply(-2, 3) == -6
    assert multiply(0, 5) == 0
    assert multiply(2.5, 4) == 10.0

def test_divide():
    """测试除法函数"""
    assert divide(6, 3) == 2
    assert divide(5, 2) == 2.5
    assert divide(0, 5) == 0
    assert divide(10, 4) == 2.5

def test_divide_by_zero():
    """测试除数为0的情况"""
    with pytest.raises(ValueError) as exc_info:
        divide(5, 0)
    assert str(exc_info.value) == "除数不能为0"

def test_all_functions():
    """综合测试所有函数"""
    # 加法
    assert add(10, 20) == 30
    # 减法
    assert subtract(20, 10) == 10
    # 乘法
    assert multiply(5, 4) == 20
    # 除法
    assert divide(20, 4) == 5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
