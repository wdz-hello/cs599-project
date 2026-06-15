"""Code quality evaluation — benchmark and metrics for generated code."""

import ast
import re
from typing import Any


class CodeBenchmark:
    """Evaluates generated code on multiple quality dimensions."""

    def evaluate_code(self, code: str, language: str = "python") -> dict:
        """Evaluate a single code snippet.

        Args:
            code: The source code to evaluate.
            language: Programming language (only 'python' supported).

        Returns:
            Dict with 'score', 'metrics', and 'issues' keys.
        """
        if language not in ("python", "py"):
            return {"score": 0, "metrics": {}, "issues": [f"Language {language} not supported for static analysis"]}

        metrics = {}
        issues = []

        # 1. Syntax validity
        syntax_ok, syntax_error = self._check_syntax(code)
        metrics["syntax_valid"] = syntax_ok
        if not syntax_ok:
            issues.append(f"Syntax error: {syntax_error}")
            return {"score": 0, "metrics": metrics, "issues": issues}

        # 2. Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"score": 0, "metrics": metrics, "issues": ["AST parse failed"]}

        # 3. Line count
        lines = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
        metrics["line_count"] = len(lines)

        # 4. Function count
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        metrics["function_count"] = len(functions)

        # 5. Class count
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        metrics["class_count"] = len(classes)

        # 6. Import count
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        metrics["import_count"] = len(imports)

        # 7. Docstring presence
        has_docstrings = 0
        for func in functions:
            if (func.body and isinstance(func.body[0], ast.Expr)
                    and isinstance(func.body[0].value, (ast.Constant, ast.Str))):
                has_docstrings += 1
        metrics["docstring_coverage"] = (has_docstrings / len(functions) * 100) if functions else 100

        # 8. Type annotation presence
        annotated_params = 0
        total_params = 0
        for func in functions:
            for arg in func.args.args:
                total_params += 1
                if arg.annotation:
                    annotated_params += 1
        metrics["type_annotation_rate"] = (annotated_params / total_params * 100) if total_params else 100

        # 9. Average function length (lines)
        func_lines = []
        for func in functions:
            if func.end_lineno and func.lineno:
                func_lines.append(func.end_lineno - func.lineno + 1)
        metrics["avg_function_length"] = (sum(func_lines) / len(func_lines)) if func_lines else 0

        # 10. Security checks
        security_issues = self._check_security(code)
        issues.extend(security_issues)
        metrics["security_issues"] = len(security_issues)

        # Calculate score
        score = self._calculate_score(metrics, issues)
        metrics["issues_count"] = len(issues)

        return {
            "score": round(score, 1),
            "metrics": metrics,
            "issues": issues,
        }

    def evaluate_test_quality(self, test_code: str, source_code: str) -> dict:
        """Assess test coverage intent by comparing test code against source.

        Args:
            test_code: The pytest test code.
            source_code: The original source code under test.

        Returns:
            Dict with estimated coverage and suggestions.
        """
        # Extract function names from source
        source_funcs = set()
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        source_funcs.add(node.name)
        except SyntaxError:
            source_funcs = set()

        # Check which functions have corresponding tests
        tested_funcs = set()
        for func_name in source_funcs:
            # Look for test_<func_name> pattern
            pattern = re.compile(rf'def\s+test_.*{re.escape(func_name)}', re.IGNORECASE)
            if pattern.search(test_code):
                tested_funcs.add(func_name)

        coverage = (len(tested_funcs) / len(source_funcs) * 100) if source_funcs else 100
        suggestions = []

        untested = source_funcs - tested_funcs
        if untested:
            suggestions.append(f"Missing tests for: {', '.join(sorted(untested))}")

        if coverage < 50:
            suggestions.append("Test coverage is low — consider adding more test cases")

        return {
            "estimated_coverage": round(coverage, 1),
            "tested_functions": sorted(tested_funcs),
            "untested_functions": sorted(untested),
            "suggestions": suggestions,
            "passed": coverage >= 70,
        }

    def run_benchmark_suite(self, test_cases: list[dict]) -> dict:
        """Run a suite of evaluation test cases and report aggregate metrics.

        Args:
            test_cases: List of dicts, each with 'code' and optional 'language' and 'label'.

        Returns:
            Aggregate benchmark results.
        """
        if not test_cases:
            return {"avg_score": 0, "total": 0, "details": []}

        results = []
        scores = []

        for tc in test_cases:
            code = tc.get("code", "")
            language = tc.get("language", "python")
            label = tc.get("label", "unnamed")

            evaluation = self.evaluate_code(code, language)
            evaluation["label"] = label
            results.append(evaluation)
            scores.append(evaluation["score"])

        return {
            "avg_score": round(sum(scores) / len(scores), 1),
            "min_score": min(scores),
            "max_score": max(scores),
            "total": len(test_cases),
            "pass_rate": round(sum(1 for s in scores if s >= 75) / len(scores) * 100, 1),
            "details": results,
        }

    @staticmethod
    def _check_syntax(code: str) -> tuple[bool, str]:
        """Check Python syntax validity."""
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, str(e)

    @staticmethod
    def _check_security(code: str) -> list[str]:
        """Check for common security issues."""
        issues = []
        code_lower = code.lower()

        patterns = [
            (r'(?:api_?key|secret|password|token)\s*=\s*["\'](?!.*os\.environ|.*getenv)[^\'"]{8,}', "Hardcoded secret detected"),
            (r'eval\s*\(', "Use of eval() is potentially dangerous"),
            (r'exec\s*\(', "Use of exec() is potentially dangerous"),
            (r'__import__\s*\(', "Dynamic import may be unsafe"),
            (r'os\.system\s*\(', "os.system() can lead to command injection"),
            (r'subprocess\.call\s*\(\s*[\'"]', "subprocess with string shell=True may be unsafe"),
        ]

        for pattern, message in patterns:
            if re.search(pattern, code):
                issues.append(message)

        return issues

    @staticmethod
    def _calculate_score(metrics: dict, issues: list) -> float:
        """Calculate an aggregate quality score from metrics."""
        score = 100.0

        # Syntax: pass/fail
        if not metrics.get("syntax_valid", True):
            return 0

        # Deduct for issues
        score -= len(issues) * 10

        # Function count bonus
        func_count = metrics.get("function_count", 0)
        if func_count == 0:
            score -= 15

        # Docstring coverage
        doc_cov = metrics.get("docstring_coverage", 0)
        if doc_cov < 50:
            score -= 10

        # Type annotation rate
        type_rate = metrics.get("type_annotation_rate", 0)
        if type_rate < 30:
            score -= 5

        # Long functions penalty
        avg_len = metrics.get("avg_function_length", 0)
        if avg_len > 50:
            score -= 10

        # Line count sanity
        line_count = metrics.get("line_count", 0)
        if line_count < 3:
            score -= 20

        return max(0, min(100, score))
