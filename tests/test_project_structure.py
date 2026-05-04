import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_directories_exist():
    """All required directories must exist."""
    required = ["conf", "infra", "memory", "core", "generation", "ui", "scripts", "tests"]
    for d in required:
        assert os.path.isdir(os.path.join(PROJECT_ROOT, d)), f"Missing directory: {d}"


def test_init_files_exist():
    """All new package directories must have __init__.py."""
    packages = ["conf", "infra", "memory", "core", "generation", "ui", "scripts", "tests"]
    for p in packages:
        init_path = os.path.join(PROJECT_ROOT, p, "__init__.py")
        assert os.path.isfile(init_path), f"Missing __init__.py in {p}"


def test_templates_exist():
    """Template files must exist."""
    templates = [
        "conf/bot.yaml.template",
        "conf/character.yaml.template",
        "conf/group_name.yaml.template",
        "conf/prompt.yaml",
    ]
    for t in templates:
        assert os.path.isfile(os.path.join(PROJECT_ROOT, t)), f"Missing template: {t}"


def test_legacy_directory_exists():
    """Legacy code must be preserved in _legacy/."""
    assert os.path.isdir(os.path.join(PROJECT_ROOT, "_legacy")), "Missing _legacy directory"
