import xml.etree.ElementTree as ET

tree = ET.parse('/Users/gabrielramos/BotSalinha/repomix-output.xml')
root = tree.getroot()

with open('/Users/gabrielramos/BotSalinha/plans/extracted_summary.txt', 'w', encoding='utf-8') as f:
    for file in root.findall('.//file'):
        path = file.get('path')
        f.write(f"--- {path} ---\n")
        text = file.text if file.text else ''
        f.write(text[:1500] + "\n\n")
