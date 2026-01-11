# E2E Test Suite

This directory contains end-to-end tests for the atloop system, ranging from simple to complex scenarios.

## Test Cases

### Test 1: Basic File Write and Edit
**Prompt**: 将"hello world"写入文件1.txt，然后将"hello"替换为"hi"，保存文件
**Expected**: File 1.txt contains "hi world"
**Difficulty**: ⭐ Easy

### Test 2: Python Function Creation
**Prompt**: 创建一个名为greeting.py的Python文件，内容包含一个函数greet(name)，返回"Hello, {name}!"，然后运行这个文件测试函数是否正常工作
**Expected**: greeting.py exists with greet function, runs successfully
**Difficulty**: ⭐ Easy

### Test 3: Multi-file Python Project
**Prompt**: 创建两个文件：main.py和utils.py。main.py导入utils.py中的函数add(a, b)，并调用它打印结果。utils.py包含add函数实现。然后运行main.py验证功能。
**Expected**: Both files exist, main.py imports and uses add from utils.py
**Difficulty**: ⭐⭐ Medium

### Test 4: JSON File Handling
**Prompt**: 创建一个config.json文件，内容为{"name": "test", "version": "1.0"}，然后创建一个read_config.py文件读取并打印这个JSON文件的内容
**Expected**: config.json and read_config.py exist, read_config.py can read JSON
**Difficulty**: ⭐⭐ Medium

### Test 5: Calculator with Tests
**Prompt**: 创建一个calculator.py文件，包含add、subtract、multiply、divide四个函数，然后创建一个test_calculator.py文件测试这些函数，最后运行测试文件验证所有功能
**Expected**: calculator.py with 4 functions, test_calculator.py with tests, tests pass
**Difficulty**: ⭐⭐ Medium

### Test 6: Project Structure
**Prompt**: 创建一个README.md文件，内容包含项目名称、描述和安装说明。然后创建一个setup.py文件，包含基本的项目元数据。最后创建一个main.py文件，打印"Project initialized successfully"
**Expected**: README.md, setup.py, and main.py exist with appropriate content
**Difficulty**: ⭐⭐ Medium

### Test 7: File Processing
**Prompt**: 创建一个data.txt文件，内容为"Line 1\nLine 2\nLine 3"，然后创建一个process_data.py文件读取data.txt，将每行转换为大写，并写入output.txt文件
**Expected**: data.txt, process_data.py, and output.txt exist, output.txt contains uppercase lines
**Difficulty**: ⭐⭐ Medium

### Test 8: Object-Oriented Programming
**Prompt**: 创建一个包含类的Python文件：创建一个Animal类，有name和sound属性，以及一个make_sound方法。然后创建一个Dog类继承Animal，sound为"Woof"。最后创建一个test.py实例化Dog并调用make_sound方法
**Expected**: Python file with Animal and Dog classes, test.py instantiates and tests
**Difficulty**: ⭐⭐⭐ Hard

### Test 9: Error Handling
**Prompt**: 创建一个包含错误处理的程序：创建一个divide.py文件，包含一个safe_divide函数，接受两个参数，如果除数为0则返回None并打印错误信息，否则返回结果。然后创建一个test_divide.py测试正常情况和除零情况
**Expected**: divide.py with error handling, test_divide.py tests both cases
**Difficulty**: ⭐⭐⭐ Hard

### Test 10: Complete Project Structure
**Prompt**: 创建一个完整的项目结构：创建src目录下的main.py和utils.py，main.py导入utils中的helper函数，utils.py包含helper函数。创建tests目录下的test_utils.py测试utils.py。创建requirements.txt文件。最后运行测试验证项目结构
**Expected**: Complete project structure with src/, tests/, requirements.txt, tests pass
**Difficulty**: ⭐⭐⭐⭐ Very Hard

### Test Order: Action Ordering
**Prompt**: 创建一个base.py文件，内容为"class Base:\n    pass"。然后使用append_file在文件末尾追加"class Derived(Base):\n    pass"。最后使用edit_file将"class Base"替换为"class Base(object)"。验证最终文件内容正确。
**Expected**: Actions executed in order: write_file -> append_file -> edit_file
**Difficulty**: ⭐⭐ Medium (tests action ordering)

## Running Tests

### Run a single test:
```bash
uv run atloopc execute --workspace ./e2e_test/test_1 --prompt-file ./e2e_test/test_1_prompt.txt --local-test
```

### Run all tests:
```bash
python3 e2e_test/run_all_tests.py
```

### Run tests with shell script:
```bash
./e2e_test/run_tests.sh
```

## Test Results

Test results and logs are saved in:
- Individual test outputs: `test_${N}_output.log`
- Summary report: `test_report.txt`

## Notes

- All tests use `--local-test` flag to run in local environment
- Workspace directories must exist (even if empty) before running tests
- Tests have timeout limits (180-300 seconds) to prevent hanging
- Each test verifies both execution success and expected outputs
