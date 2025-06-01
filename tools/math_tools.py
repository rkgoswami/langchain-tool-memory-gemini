from langchain_core.tools import tool

@tool
def custom_add(a: int, b: int) -> int:
    """Adds two integers."""
    return a + b

@tool
def custom_divide(a: int, b: int) -> float:
    """Divides two integers."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b

