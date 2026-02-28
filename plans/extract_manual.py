import re

with open('/Users/gabrielramos/BotSalinha/repomix-output.xml', 'r', encoding='utf-8') as f:
    content = f.read()

# O formato do repomix-output costuma ter tags <file path="..."></file>
files = re.findall(r'<file path="([^"]+)">\n(.*?)\n</file>', content, re.DOTALL)

with open('/Users/gabrielramos/BotSalinha/plans/extracted_summary.txt', 'w', encoding='utf-8') as f:
    for path, text in files:
        f.write(f"--- {path} ---\n")
        lines = text.split('\n')
        # Pega as primeiras 50 linhas ou o código inteiro se for menor
        f.write('\n'.join(lines[:50]) + "\n\n")

print(f"Extraídos {len(files)} arquivos.")
