from constants import *
def Info(message: str) -> None:
    print("[INFO]", message)

    return  
def Warn(message: str) -> None:
    print("[WARN]", message)

    return
def Error(message: str) -> None:
    print("[ERROR]", message)

    return
def Fatal(message: str) -> None:
    print("[FATAL]", message)

    return
def Debug(message: str) -> None:
    print("[DEBUG]", message)

    return

def error(content: str) -> str:
    return ERROR + content
def success(content: str) -> str:
    return SUCCESS + content