
import os

replacements = {
    'Ã§': 'ç',
    'Ã‡': 'Ç',
    'ÄŸ': 'ğ',
    'Ä°': 'İ',
    'Ä±': 'ı',
    'Ã¶': 'ö',
    'Ã–': 'Ö',
    'ÅŸ': 'ş',
    'Å': 'Ş',
    'Ã¼': 'ü',
    'Ãœ': 'Ü',
    'â€“': '–', # en dash
    'â€™': "'", # right single quote
     # Additional common double encoding artifacts
    'Â': '', 
    'Ã¢': 'â'
}

def fix_encoding(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Check if file has corruption
        if 'Ã' in content or 'ÅŸ' in content:
            print(f"Fixing {filepath}...")
            for bad, good in replacements.items():
                content = content.replace(bad, good)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print("Fixed.")
        else:
            print(f"No corruption found in {filepath}")
            
    except Exception as e:
        print(f"Error fixing {filepath}: {e}")

fix_encoding('admin/index.html')
# Script js seems fine now but check anyway
fix_encoding('admin/script.js')
