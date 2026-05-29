# logic/data_models.py
from typing import List, Dict, Any

class TemplateField:
    def __init__(self, name: str, display_name: str = "", field_type: str = "text", required: bool = False):
        self.name = name
        self.display_name = display_name or name
        self.field_type = field_type
        self.required = required

    def to_dict(self):
        return {"name": self.name, "display_name": self.display_name, "type": self.field_type, "required": self.required}

    @staticmethod
    def from_dict(data):
        return TemplateField(data["name"], data["display_name"], data["type"], data["required"])


class TemplateBlock:
    def __init__(self, name: str, fields: List[TemplateField], display_name: str = ""):
        self.name = name
        self.display_name = display_name or name
        self.fields = fields

    def to_dict(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "fields": [f.to_dict() for f in self.fields]
        }

    @staticmethod
    def from_dict(data):
        fields = [TemplateField.from_dict(f) for f in data["fields"]]
        return TemplateBlock(data["name"], fields, data.get("display_name", data["name"]))


class Template:
    def __init__(self, id: str, name: str, file_path: str, fields: List[TemplateField], blocks: List[TemplateBlock]):
        self.id = id          # теперь это будет полный путь к файлу
        self.name = name
        self.file_path = file_path
        self.fields = fields
        self.blocks = blocks

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "file_path": self.file_path,
            "fields": [f.to_dict() for f in self.fields],
            "blocks": [b.to_dict() for b in self.blocks]
        }

    @staticmethod
    def from_dict(data):
        fields = [TemplateField.from_dict(f) for f in data["fields"]]
        blocks = [TemplateBlock.from_dict(b) for b in data["blocks"]]
        return Template(data["id"], data["name"], data["file_path"], fields, blocks)