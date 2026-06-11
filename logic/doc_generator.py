from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
import os

def generate_docx(template_path, data_dict, output_path):
    doc = DocxTemplate(template_path)
    # Обработка картинок: если значение в data_dict — это путь к существующему файлу изображения,
    # заменяем его на InlineImage
    for key, value in data_dict.items():
        if isinstance(value, str) and value.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            if os.path.exists(value):
                try:
                    data_dict[key] = InlineImage(doc, value, width=Inches(1.5))  # можно задать ширину по умолчанию
                except:
                    pass
    doc.render(data_dict)
    doc.save(output_path)