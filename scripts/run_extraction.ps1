$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'TrialFlow: downloading 25 real ClinicalTrials.gov studies and reported locations...'
python -m pip install requests
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
python .\extract_trials.py
if ($LASTEXITCODE -ne 0) { throw 'Trial extraction failed. Check the API connection and error above.' }
python -c "import csv,json,pathlib; p=pathlib.Path('.'); t=list(csv.DictReader((p/'trials.csv').open(encoding='utf-8'))); s=list(csv.DictReader((p/'sites.csv').open(encoding='utf-8'))); ids={x['nct_id'] for x in t}; assert len(t)==25 and len(ids)==25; assert s and all(x['nct_id'] in ids for x in s); print(f'VERIFIED: {len(t)} unique trials and {len(s)} linked site rows'); print('FILES:',*[str(x.resolve()) for x in [p/'trials.csv',p/'sites.csv',p/'raw_25_studies.json',p/'sample_metadata.json']],sep='\n  ')"
if ($LASTEXITCODE -ne 0) { throw 'Output validation failed.' }
