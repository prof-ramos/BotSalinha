import re

with open('/Users/gabrielramos/BotSalinha/repomix-output.xml', 'r', encoding='utf-8') as f:
    content = f.read()

# O padrao sugerido pela repomix é diferent: no XML as tags variam
# Vamos tentar extrair qualquer node 'file' de um outro jeito simples.
files = re.findall(r'<file\s+path="([^"]+)">\n(.*?)\n</file>', content, re.DOTALL)

with open('/Users/gabrielramos/BotSalinha/plans/extracted_summary.txt', 'w', encoding='utf-8') as f:
    for path, text in files:
        f.write(f"--- {path} ---\n")
        lines = text.split('\n')
        f.write('\n'.join(lines[:50]) + "\n\n")

print(f"Extraídos {len(files)} arquivos.")
