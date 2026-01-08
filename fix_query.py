import re

with open(r'c:\Users\pinot\WEB_CAPSTONE\CAPSTONE_DENRO\DENRO\views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix CENRO
content = re.sub(
    r"LEFT JOIN enumerators_report er ON eh\.change_reason LIKE '%Report ' \|\| er\.id \|\| '%' LEFT JOIN users u ON er\.enumerator_id = u\.id WHERE \(u\.cenro_id = %s OR u\.cenro_id IS NULL\)\"\"\"\s+params = \[cenro_id\]",
    'WHERE 1=1"""\n        params = []',
    content
)

# Fix PENRO
content = re.sub(
    r"LEFT JOIN enumerators_report er ON eh\.change_reason LIKE '%Report ' \|\| er\.id \|\| '%' LEFT JOIN users u ON er\.enumerator_id = u\.id WHERE \(u\.penro_id = %s OR u\.penro_id IS NULL\)\"\"\"\s+params = \[penro_id\]",
    'WHERE 1=1"""\n        params = []',
    content
)

# Fix Admin
content = re.sub(
    r"LEFT JOIN enumerators_report er ON eh\.change_reason LIKE '%Report ' \|\| er\.id \|\| '%' LEFT JOIN users u ON er\.enumerator_id = u\.id WHERE \(u\.region_id = %s OR u\.region_id IS NULL\)\"\"\"\s+params = \[region_id\]",
    'WHERE 1=1"""\n        params = []',
    content
)

with open(r'c:\Users\pinot\WEB_CAPSTONE\CAPSTONE_DENRO\DENRO\views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")
