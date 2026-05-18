with open('dashboard/src/pages/NarrativeBrief.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(r'\`', '`')
content = content.replace(r'\$', '$')

with open('dashboard/src/pages/NarrativeBrief.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
