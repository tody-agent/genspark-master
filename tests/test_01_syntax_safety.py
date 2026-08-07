import importlib
import pkgutil
import pytest

def test_syntax_safety():
    """
    Layer 1: Frontend/Syntax Safety check.
    Ensures that all modules in the genspark_cli package can be imported
    without syntax errors, catastrophic corruption, or circular dependency issues.
    """
    import genspark_cli
    
    package = genspark_cli
    prefix = package.__name__ + "."
    
    # Walk all submodules and attempt to import them
    for _, modname, _ in pkgutil.walk_packages(package.__path__, prefix):
        try:
            importlib.import_module(modname)
        except ImportError as e:
            pytest.fail(f"Could not import module {modname} due to ImportError: {e}")
        except SyntaxError as e:
            pytest.fail(f"Syntax error found in {modname}: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error when importing {modname}: {e}")
