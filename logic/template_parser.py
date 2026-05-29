# logic/template_parser.py
import re
import zipfile
from xml.etree import ElementTree as ET
from logic.data_models import TemplateField, TemplateBlock


def parse_docx_template(docx_path):
    """
    Возвращает (fields, blocks):
        fields: список TemplateField в порядке появления в документе
        blocks: список TemplateBlock в порядке появления
    """
    full_text = extract_text_from_docx(docx_path)

    # 1. Ищем блоки {% for ... %}...{% endfor %} и вырезаем их
    block_pattern = r'\{\%\s*for\s+(\w+)\s+in\s+(\w+)\s*\%\}(.*?)\{\%\s*endfor\s*\%\}'
    blocks = []

    # Функция замены: для каждого блока сохраняем его, в тексте заменяем на пустую строку
    def replace_block(match):
        item_var = match.group(1)  # например, source
        list_name = match.group(2)  # например, sources
        inner_text = match.group(3)

        # Ищем поля вида {{ item_var.field }}
        field_names = re.findall(r'\{\{\s*' + item_var + r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}', inner_text)
        # Убираем дубликаты, сохраняя порядок
        unique_field_names = list(dict.fromkeys(field_names))
        if unique_field_names:
            block_fields = [TemplateField(name=f) for f in unique_field_names]
            blocks.append(TemplateBlock(name=list_name, fields=block_fields))
        return ""  # удаляем содержимое блока из текста при поиске простых полей

    # Удаляем блоки из текста и одновременно заполняем blocks
    text_without_blocks = re.sub(block_pattern, replace_block, full_text, flags=re.DOTALL)

    # 2. В оставшемся тексте ищем простые поля {{ var }}
    # Находим все вхождения в порядке появления
    simple_var_matches = re.findall(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}', text_without_blocks)
    # Убираем дубликаты, сохраняя порядок первого вхождения
    unique_simple_vars = list(dict.fromkeys(simple_var_matches))
    fields = [TemplateField(name=v) for v in unique_simple_vars]

    return fields, blocks


def extract_text_from_docx(docx_path):
    """Извлекает весь текст из .docx файла, возвращает строку"""
    text = []
    with zipfile.ZipFile(docx_path, 'r') as docx_zip:
        with docx_zip.open('word/document.xml') as xml_file:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for para in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                para_text = ''.join(
                    t.text for t in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if
                    t.text)
                if para_text:
                    text.append(para_text)
    return '\n'.join(text)