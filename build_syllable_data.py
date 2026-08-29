"""Build syllable data from CMU Pronouncing Dictionary."""
import urllib.request
import sys
from pathlib import Path

URL = 'http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b'
VOWEL_PHONEMES = {'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY', 'IH', 'IY', 'OW', 'OY', 'UH', 'UW'}

print("Downloading CMU Pronouncing Dictionary...")
resp = urllib.request.urlopen(URL, timeout=30)
raw = resp.read()
text = raw.decode('latin-1')
lines = text.splitlines()

entries = [l for l in lines if l and not l.startswith(';;;')]
print(f"Total raw entries: {len(entries)}")

syllable_map = {}
for entry in entries:
    parts = entry.split()
    if len(parts) < 2:
        continue
    word = parts[0].lower()
    if '(' in word:
        word = word[:word.index('(')]
    phonemes = parts[1:]
    syllable_count = sum(1 for p in phonemes if p.rstrip('012') in VOWEL_PHONEMES)
    if syllable_count > 0:
        syllable_map[word] = syllable_count

print(f"Unique words: {len(syllable_map)}")

# Verify some known trouble words
checks = ['every', 'people', 'business', 'information', 'the', 'water',
          'beautiful', 'through', 'though', 'colonel', 'interesting']
for w in checks:
    print(f"  {w}: {syllable_map.get(w, 'NOT FOUND')}")

# Write a compact format: marshal the dict for fast loading
import marshal

# Write binary data file
bin_path = Path(__file__).parent / 'plainspeak' / 'core' / 'syllable_data.bin'
with open(bin_path, 'wb') as f:
    marshal.dump(syllable_map, f)

# Write a thin Python wrapper
out_path = Path(__file__).parent / 'plainspeak' / 'core' / 'syllables.py'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('"""\n')
    f.write('Pre-computed syllable counts from the CMU Pronouncing Dictionary.\n')
    f.write(f'\n')
    f.write(f'Source: {URL}\n')
    f.write(f'Words: {len(syllable_map)}\n')
    f.write('Uses Python marshal format for fast loading (~50ms vs ~1200ms for .py).\n')
    f.write('Generated automatically — do not edit by hand.\n')
    f.write('"""\n')
    f.write('\n')
    f.write('import marshal\n')
    f.write('from pathlib import Path\n')
    f.write('\n')
    f.write('_SYLLABLE_COUNT: dict[str, int] | None = None\n')
    f.write('\n')
    f.write('\n')
    f.write('def get_syllable_count() -> dict[str, int]:\n')
    f.write('    """Return the syllable count dictionary, loading from binary on first call."""\n')
    f.write('    global _SYLLABLE_COUNT\n')
    f.write('    if _SYLLABLE_COUNT is None:\n')
    f.write('        _data_path = Path(__file__).parent / "syllable_data.bin"\n')
    f.write('        with open(_data_path, "rb") as _f:\n')
    f.write('            _SYLLABLE_COUNT = marshal.load(_f)\n')
    f.write('    return _SYLLABLE_COUNT\n')

print(f"\nWritten {len(syllable_map)} entries")
print(f"Binary: {bin_path.stat().st_size / 1024:.0f} KB")
print(f"Wrapper: {out_path.stat().st_size / 1024:.0f} KB")
