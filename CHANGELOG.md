# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0] - 2025-01-XX

### Added
- **Memory formatting cache**: Performance optimization with automatic cache invalidation
  - Cache hit rate tracking and statistics
  - FIFO eviction policy (max 10 entries)
- **Performance benchmarks**: Comprehensive benchmark suite for memory formatting
  - Small, medium, and large memory benchmarks
  - Cache performance validation
- **Error metrics collection**: Structured error tracking and reporting
  - Error categorization by type, phase, and category
  - Error summary statistics for debugging
- **Security scanning**: Automated security vulnerability detection
  - Weekly `pip-audit` scans for dependency vulnerabilities
  - `bandit` code security analysis
- **Dependency automation**: Dependabot configuration for automated updates
  - Weekly Python dependency updates
  - Monthly GitHub Actions updates
- **Performance profiling tools**: Scripts for performance analysis
  - Memory formatting profiler with cProfile integration
- **Type safety improvements**: Enhanced type checking infrastructure
  - PEP 561 marker file (`py.typed`)
  - Stricter mypy configuration
  - Type checking in CI pipeline
- **Pre-commit hooks**: Automated code quality checks before commits
  - Ruff linting and formatting
  - File consistency checks

### Changed
- **Exception handling**: Replaced all broad `except Exception:` with specific exception types
  - Improved error handling precision
  - Better debugging and error recovery
- **Error messages**: Enhanced error context and clarity
  - More detailed error information for LLM
  - Better error categorization
- **Code quality**: Fixed all 79 ruff violations
  - Zero code quality issues
  - Consistent code formatting
- **Test coverage**: Enforced 60% minimum coverage threshold
  - Coverage tracking in CI
  - Improved test reliability

### Fixed
- Fixed test failures after Phase 1 improvements
  - Updated ConsoleOutputHandler tests for new API
  - Fixed ToolExecutor mock dependencies
  - Adjusted code quality validation thresholds
  - Fixed placeholder extraction test expectations

## [v0.1.0] - 2024-XX-XX

### Added
- Initial release of atloop
- CLI interface (`atloopc`)
- Python API (`TaskRunner`)
- Support for bugfix, feature, and refactor task types
- Sandbox execution with isolation
- Memory management with compression
- Tool ecosystem with auto-discovery
- Budget management
- Complete documentation

### Changed
- Renamed from titan to atloop

[Unreleased]: https://github.com/lzjever/atloop/compare/v0.2.0...HEAD
[v0.2.0]: https://github.com/lzjever/atloop/compare/v0.1.0...v0.2.0
