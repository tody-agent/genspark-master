import pytest
import os
import re
import subprocess
from pathlib import Path

def test_no_secret_files_tracked():
    """Layer 5: Ensure secret files aren't tracked by git."""
    try:
        # If not a git repo, skip securely
        tracked = subprocess.check_output(['git', 'ls-files'], text=True)
    except subprocess.CalledProcessError:
        pytest.skip("Not inside a git repository.")
    
    bad_files = ['.env', '.dev.vars', '.env.local', '.env.production', 'cookies.json']
    tracked_files = tracked.split('\n')
    
    found = [f for f in bad_files if f in tracked_files]
    assert not found, f"Secret files tracked by git: {', '.join(found)}"

def test_gitignore_contains_required_patterns():
    """Layer 5: Ensure .gitignore contains minimum security patterns."""
    gitignore_path = Path('.gitignore')
    if not gitignore_path.exists():
        pytest.skip(".gitignore not found.")
        
    content = gitignore_path.read_text()
    assert '.env' in content, ".gitignore missing .env"

def test_no_hardcoded_secrets_in_source():
    """Layer 5: Deep regex scan for hardcoded secrets in source files."""
    dangerous_patterns = [
        re.compile(r"SERVICE_KEY\s*[=:]\s*['\"][a-zA-Z0-9/+=]{20,}['\"]"),
        re.compile(r"PRIVATE_KEY\s*[=:]\s*['\"][a-zA-Z0-9/+=]{20,}['\"]"),
        re.compile(r"-----BEGIN.*PRIVATE KEY-----"),
        re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"), # JWT Tokens
        re.compile(r"api[_-]?key\s*[=:]\s*['\"][a-zA-Z0-9/+=]{20,}['\"]", re.IGNORECASE)
    ]
    
    src_dir = Path('genspark_cli')
    if not src_dir.exists():
        pytest.skip("Source directory not found.")
        
    for py_file in src_dir.rglob('*.py'):
        content = py_file.read_text(encoding='utf-8', errors='ignore')
        for pattern in dangerous_patterns:
            matches = pattern.findall(content)
            # Ensure no matches
            assert not matches, f"Potential secret found in {py_file} matching {pattern.pattern}"

def test_no_placeholder_values_committed():
    """Layer 5: Prevent fake keys from being committed inside code"""
    dangerous_patterns = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}")
    ]
    
    src_dir = Path('genspark_cli')
    if not src_dir.exists():
        pytest.skip("Source directory not found.")
        
    for py_file in src_dir.rglob('*.py'):
        content = py_file.read_text(encoding='utf-8', errors='ignore')
        for pattern in dangerous_patterns:
            matches = pattern.findall(content)
            assert not matches, f"Potential OpenAI/fake token found in {py_file}"
