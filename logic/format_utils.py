# logic/format_utils.py
"""Общее форматирование значений для шаблонов.

Используется и в форме (ui/form_builder.py), и в массовой генерации
(ui/mass_generate_dialog.py), чтобы результаты совпадали.
"""
import re
from datetime import datetime, date


RU_MONTHS_FULL = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]
RU_MONTHS_SHORT = [
    'янв', 'фев', 'мар', 'апр', 'мая', 'июн',
    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
]


def _to_datetime(value):
    """Приводит разные типы к datetime. None, если не получилось."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    # pandas.Timestamp
    if hasattr(value, 'to_pydatetime'):
        return value.to_pydatetime()
    # QDate и подобные
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        y, m, d = value.year(), value.month(), value.day()
        return datetime(y, m, d)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y",
                    "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def format_date(value, fmt):
    """Форматирует дату. Пустой fmt → DD.MM.YYYY.

    Русские названия месяцев подставляются вручную (независимо от локали).
    """
    dt = _to_datetime(value)
    if dt is None:
        return str(value) if value is not None else ""

    if not fmt:
        return dt.strftime("%d.%m.%Y")

    # Месяцы: подменяем %B/%b на плейсхолдеры, форматируем остальное,
    # потом возвращаем русские названия. Так не зависим от локали системы.
    if '%B' in fmt or '%b' in fmt:
        tmp = fmt.replace('%B', '\x00F\x00').replace('%b', '\x00S\x00')
        try:
            result = dt.strftime(tmp)
        except Exception:
            return dt.strftime("%d.%m.%Y")
        result = result.replace('\x00F\x00', RU_MONTHS_FULL[dt.month - 1])
        result = result.replace('\x00S\x00', RU_MONTHS_SHORT[dt.month - 1])
        return result

    try:
        return dt.strftime(fmt)
    except Exception:
        return dt.strftime("%d.%m.%Y")


def format_number(value, fmt):
    """Форматирует число. Русская нотация применяется, если в fmt
    есть разделитель тысяч (запятая в format_spec).

    Соответствует описанию в help.html:
        {}          → 1234.56
        {:,.0f}     → 1 235
        {:,.2f}     → 1 234,56
        {:,.2f} руб.→ 1 234,56 руб.
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""

    if fmt:
        try:
            formatted = fmt.format(num)
        except Exception:
            formatted = str(num)
    else:
        formatted = str(int(num)) if num == int(num) else f"{num:.2f}"

    # Русская нотация только если в fmt реально использован разделитель тысяч
    if fmt and re.search(r'\{:[^}]*,[^}]*\}', fmt):
        formatted = _russian_notation(formatted)

    return formatted


def _russian_notation(s):
    """1,234,567.89 → 1 234 567,89"""
    # Запятые-разделители тысяч (между цифрами, перед группой 3)
    s = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', ' ', s)
    # Точка-разделитель дробной части (между цифрами) → запятая
    s = re.sub(r'(?<=\d)\.(?=\d)', ',', s)
    return s

def strftime_to_qt_format(fmt):
    """Конвертирует strftime-формат в Qt displayFormat для QDateEdit.

    Примеры:
        %d.%m.%Y  → dd.MM.yyyy
        %d %B %Y  → dd MMMM yyyy
        %Y-%m-%d  → yyyy-MM-dd
    """
    if not fmt:
        return "dd.MM.yyyy"

    result = fmt
    # Порядок важен: сначала длинные токены, иначе %Y съест часть %y
    replacements = [
        ('%Y', 'yyyy'),
        ('%y', 'yy'),
        ('%B', 'MMMM'),
        ('%b', 'MMM'),
        ('%m', 'MM'),
        ('%d', 'dd'),
        ('%H', 'HH'),
        ('%M', 'mm'),
        ('%S', 'ss'),
    ]
    for py, qt in replacements:
        result = result.replace(py, qt)
    return result