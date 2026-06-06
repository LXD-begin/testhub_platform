import json
import re


VARIABLE_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')


class CaseContext:
    def __init__(self):
        self.variables = {}
        self.finished_cases = set()

    def set(self, name, value):
        self.variables[name] = value

    def get(self, name):
        return self.variables[name]

    def mark_finished(self, case_id):
        self.finished_cases.add(case_id)

    def is_finished(self, case_id):
        return not case_id or case_id in self.finished_cases

    def render(self, value):
        if isinstance(value, str):
            return VARIABLE_PATTERN.sub(lambda match: str(self.get(match.group(1))), value)
        if isinstance(value, dict):
            return {key: self.render(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.render(item) for item in value]
        return value

    def render_json_text(self, value):
        return json.dumps(self.render(value), ensure_ascii=False)
