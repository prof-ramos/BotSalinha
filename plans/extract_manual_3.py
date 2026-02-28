import re

with open('/Users/gabrielramos/BotSalinha/repomix-output.xml', 'r', encoding='utf-8') as f:
    content = f.read()

# Buscando conteúdo entre <file path="..."> e </file>
files = re.findall(r'<file\s+path="([^"]+)">\n(.*?)</file>', content, re.DOTALL)

with open('/Users/gabrielramos/BotSalinha/plans/extracted_summary.txt', 'w', encoding='utf-8') as f:
    for path, text in files:
        f.write(f"--- {path} ---\n")
        lines = text.split('\n')
        # Pega as primeiras 400 linhas iniciais de cada arquivo pro contexto da análise profunda
        f.write('\n'.join(lines[:400]) + "\n\n")

print(f"Extraídos {len(files)} arquivos.")
