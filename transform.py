import re

with open('dashboard/src/pages/CompanyIntelligence.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace KpiCard wrapper
content = re.sub(
    r'<div\s+style={{\s*background: \"#0F172A\", border: \"1px solid #1E293B\",\s*borderRadius: 12,\s*padding: \"16px 20px\",',
    '<div\n      className=\"ci-kpi-card\"\n      style={{\n        borderRadius: 12, padding: \"16px 20px\",',
    content
)

# Replace other glass panels
content = re.sub(
    r'<div style={{ background: \"#0F172A\", border: \"1px solid #1E293B\",',
    '<div className=\"ci-glass-panel\" style={{',
    content
)

content = re.sub(
    r'<div style={{ display: \"flex\", background: \"#0F172A\", border: \"1px solid #1E293B\",',
    '<div className=\"ci-glass-panel\" style={{ display: \"flex\", ',
    content
)

content = re.sub(
    r'style={{ background: \"#0F172A\", border: \"1px solid #1E293B\", borderRadius: 8, color: \"#94A3B8\",',
    'className=\"ci-glass-panel\" style={{ borderRadius: 8, color: \"#94A3B8\",',
    content
)

# Apply ci-gradient-text to entity name
content = re.sub(
    r'<h2 style={{ fontSize: 18, fontWeight: 700, color: \"#F1F5F9\" }}>{entity\.entity_name}</h2>',
    '<h2 className=\"ci-gradient-text\" style={{ fontSize: 24, fontWeight: 800 }}>{entity.entity_name}</h2>',
    content
)

# Signal timeline cards
content = re.sub(
    r'style={{\s*background: \"#0F172A\", border: \"1px solid #1E293B\",\s*borderRadius: 10',
    'className=\"ci-glass-panel\"\n            style={{\n              borderRadius: 10',
    content
)

# Also remove the inline background from ci-table-row
content = re.sub(
    r'background: \"rgba\(15, 23, 42, 0.4\)\",\s*border: \"1px solid #1E293B\",',
    '',
    content
)

with open('dashboard/src/pages/CompanyIntelligence.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
