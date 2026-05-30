from docxtpl import DocxTemplate

def generate_docx(template_path, data_dict, output_path):
    """
    template_path: путь к .docx шаблону
    data_dict: словарь вида { "client_name": "Иван", "books": [{"title":...}] }
    output_path: куда сохранить результат
    """
    doc = DocxTemplate(template_path)
    doc.render(data_dict)
    doc.save(output_path)
    return output_path