pytest.ini:
[pytest]
addopts = -v
testpaths = tests
python_files = test_*.py

tests/test_hello_world.py:
def test_hello_world():
    assert 1 + 1 == 2