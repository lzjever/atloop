def greet(name):
    """返回问候语"""
    return f"Hello, {name}!"

if __name__ == "__main__":
    # 测试函数
    test_name = "World"
    result = greet(test_name)
    print(f"测试: greet('{test_name}') = '{result}'")
    print("如果看到 'Hello, World!'，则函数工作正常。")
