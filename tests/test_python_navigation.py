from pathlib import Path

from tuide.services.python_navigation import PythonNavigationService


def test_goto_definition_across_files(tmp_path: Path) -> None:
    root = tmp_path
    source = root / "a.py"
    target = root / "b.py"
    target.write_text("def foo():\n    pass\n", encoding="utf-8")
    source.write_text("from b import foo\nfoo()\n", encoding="utf-8")

    service = PythonNavigationService(cache_dir=root / ".jedi-cache")
    definitions = service.goto_definition(source, source.read_text(), 2, 1, [root])

    assert [(item.path.name, item.line, item.column) for item in definitions] == [("b.py", 1, 5)]


def test_find_references_across_files(tmp_path: Path) -> None:
    root = tmp_path
    source = root / "a.py"
    target = root / "b.py"
    target.write_text("def foo():\n    pass\n", encoding="utf-8")
    source.write_text("from b import foo\nfoo()\n", encoding="utf-8")

    service = PythonNavigationService(cache_dir=root / ".jedi-cache")
    references = service.find_references(source, source.read_text(), 2, 1, [root])

    assert [(item.path.name, item.line, item.column) for item in references] == [
        ("a.py", 1, 15),
        ("a.py", 2, 1),
        ("b.py", 1, 5),
    ]
