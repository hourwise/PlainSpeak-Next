# Third-Party Notices

PlainSpeak incorporates or depends on the following third-party materials.

---

## CMU Pronouncing Dictionary (cmudict-0.7b)

- **Source:** Carnegie Mellon University Speech Group
- **URL:** http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b
- **Version:** 0.7b
- **Retrieval date:** 2026-08-11
- **Licence:** BSD-like (see below)
- **Modifications:** Converted from phoneme format to word→syllable-count mapping.
  Only syllable counts are stored, not the original phoneme transcriptions.
  Stored in Python marshal binary format for efficient loading.
- **Attribution:** The CMU Pronouncing Dictionary is Copyright (C) 1993-2015
  Carnegie Mellon University. All rights reserved.
- **Redistribution compatibility:** The CMUdict licence permits redistribution
  with attribution. The transformed syllable-count data is redistributed under
  the same terms.

### CMU Pronouncing Dictionary Licence

```
Copyright (C) 1993-2015 Carnegie Mellon University. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in
   the documentation and/or other materials provided with the
   distribution.

This work was supported in part by funding from the Defense Advanced
Research Projects Agency, the National Science Foundation of the
United States, and the C-MU Sphinx Speech Consortium.

THIS SOFTWARE IS PROVIDED BY CARNEGIE MELLON UNIVERSITY "AS IS" AND
ANY EXPRESSED OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL CARNEGIE MELLON UNIVERSITY
NOR ITS EMPLOYEES BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## Python Dependencies

PlainSpeak depends on the following Python packages. All are installed
from PyPI and are subject to their own licence terms.

### Core dependencies
| Package | Version | Licence | Usage |
|---|---|---|---|
| click | >=8.0 | BSD-3-Clause | CLI framework |

### Optional: Web interface
| Package | Version | Licence | Usage |
|---|---|---|---|
| flask | >=3.0 | BSD-3-Clause | Local web server |
| werkzeug | (flask dep) | BSD-3-Clause | WSGI utilities |
| jinja2 | (flask dep) | BSD-3-Clause | Templates (not directly used by PlainSpeak) |
| markupsafe | (flask dep) | BSD-3-Clause | HTML escaping |
| itsdangerous | (flask dep) | BSD-3-Clause | Session signing |
| blinker | (flask dep) | MIT | Signals |

### Optional: Document readers
| Package | Version | Licence | Usage |
|---|---|---|---|
| python-docx | >=0.8 | MIT | .docx text extraction |
| pypdf | >=3.0 | BSD-3-Clause | .pdf text extraction |

### Development
| Package | Version | Licence | Usage |
|---|---|---|---|
| pytest | >=7.0 | MIT | Test framework |
| pytest-cov | >=4.0 | MIT | Test coverage |

---

## Glossary Sources

PlainSpeak's plain-language glossary is curated from public guidance including:
- Plain Language Action and Information Network (PLAIN) — US government
- CDC Clear Communication Index — US government, public domain
- UK Government Digital Service (GDS) style guide — Open Government Licence
- Plain English Campaign resources — publicly available guidance

No copyrighted glossary content is reproduced. The glossary contains
independently written plain-language pairings informed by these resources.

---

## Web Application Assets

The PlainSpeak web application:
- Contains no CDN references
- Contains no external fonts, scripts, or stylesheets
- Uses only system fonts via the CSS `system-ui` font stack
- Contains no tracking, analytics, or telemetry
- Contains no third-party JavaScript libraries
- All CSS and JavaScript is inline and original

---

*This document was last updated: 2026-08-11*
