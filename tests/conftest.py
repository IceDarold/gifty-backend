import yaml
import pytest
from pathlib import Path

def pytest_configure(config):
    # Register custom markers
    config.addinivalue_line("markers", "ai_test: AI intelligence tests")
    config.addinivalue_line("markers", "slow: slow running tests")

def get_test_config():
    config_path = Path(__file__).parent.parent / "tests_config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}

def pytest_collection_modifyitems(config, items):
    test_cfg = get_test_config()
    groups = test_cfg.get("test_groups", {})
    
    tests_root = Path(__file__).parent.parent / "tests"
    for item in items:
        # Get absolute path of the test file
        item_path = Path(str(item.fspath))
        
        try:
            rel_path = item_path.relative_to(tests_root)
            group_name = rel_path.parts[0] if rel_path.parts else "root"
        except ValueError:
            # File is outside the 'tests' directory
            group_name = "other"
        
        # Mapping root-level files to 'security' group for example
        if group_name.startswith("test_"):
             group_name = "security" if "security" in group_name or "pkce" in group_name or "state" in group_name else "core"

        if group_name in groups and not groups[group_name]:
            item.add_marker(pytest.mark.skip(reason=f"Group '{group_name}' is disabled in tests_config.yaml"))
            continue

        # 2. Skip based on markers
        if item.get_closest_marker("ai_test") and not groups.get("ai_intelligence", True):
            item.add_marker(pytest.mark.skip(reason="AI Intelligence tests are disabled"))
