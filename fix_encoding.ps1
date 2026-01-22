
$path = "admin/index.html"
$content = Get-Content $path -Raw -Encoding utf8

# Define replacements
$replacements = @{
    'Ã§' = 'ç';
    'Ã‡' = 'Ç';
    'ÄŸ' = 'ğ';
    'Ä°' = 'İ';
    'Ä±' = 'ı';
    'Ã¶' = 'ö';
    'Ã–' = 'Ö';
    'ÅŸ' = 'ş';
    'Å' = 'Ş';
    'Ã¼' = 'ü';
    'Ãœ' = 'Ü';
    'â€“' = '–';
    'â€™' = "'";
    'Â' = '';
    'Ã¢' = 'â'
}

foreach ($key in $replacements.Keys) {
    $content = $content.Replace($key, $replacements[$key])
}

# Write back with UTF8 BOM to ensure Windows handles it correctly, or standard UTF8
[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))

Write-Host "Fixed encoding in $path"
