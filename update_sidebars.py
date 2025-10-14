import re
from pathlib import Path

templates_dir = Path("C:/Users/nikolai/Code/Saas_analyse/templates")

# Files to update with their active_page values
files_to_update = {
    "admin_versions.html": "admin_versions",
    "customers_all.html": "customers_all",
    "invoices_trends.html": "invoices_trends",
    "changelog.html": "changelog",
    "debug.html": "debug",
    "guide.html": "guide",
    "documents.html": "documents",
}

# CSS pattern to match and replace
css_pattern = re.compile(
    r'\.sidebar\s*{.*?}.*?'
    r'\.sidebar-logo\s*{.*?}.*?'
    r'\.sidebar-nav\s*{.*?}.*?'
    r'(\.nav-section\s*{.*?})?.*?'
    r'\.nav-section-title\s*{.*?}.*?'
    r'\.nav-link\s*{.*?}.*?'
    r'\.nav-link:hover\s*{.*?}.*?'
    r'\.nav-link\.active\s*{.*?}.*?'
    r'\.nav-link-icon\s*{.*?}.*?'
    r'\.nav-divider\s*{.*?}',
    re.DOTALL
)

# HTML pattern to match the entire sidebar div
html_pattern = re.compile(
    r'<div class="sidebar">.*?</nav>\s*</div>',
    re.DOTALL
)

for filename, active_page in files_to_update.items():
    filepath = templates_dir / filename
    if not filepath.exists():
        print(f"Skipping {filename} - file not found")
        continue

    print(f"Processing {filename}...")

    try:
        content = filepath.read_text(encoding='utf-8')
        original_content = content

        # Replace CSS styles
        content = css_pattern.sub('{% include \'sidebar_styles.html\' %}', content, count=1)

        # Replace HTML sidebar
        sidebar_replacement = f"{{% set active_page = '{active_page}' %}}\n    {{% include 'sidebar.html' %}}"
        content = html_pattern.sub(sidebar_replacement, content, count=1)

        if content != original_content:
            filepath.write_text(content, encoding='utf-8')
            print(f"[OK] Updated {filename}")
        else:
            print(f"  No changes needed for {filename}")

    except Exception as e:
        print(f"[ERROR] Error processing {filename}: {e}")

print("\nDone!")
