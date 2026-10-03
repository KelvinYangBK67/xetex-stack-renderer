"""Diagnosable package failures shared by CLI, font and script layers."""
class XSRError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f'[{code}] {detail}')
