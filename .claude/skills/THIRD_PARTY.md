# Third-party skills

These general-purpose skills are copied from other repositories under the MIT License. They are not specific to TrialFlow. Project-specific skills, when added, live alongside them.

| Skill | Source | Commit | Local changes |
|---|---|---|---|
| `systematic-debugging` | [obra/superpowers](https://github.com/obra/superpowers) `skills/systematic-debugging` | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | Dropped `CREATION-LOG.md` and `test-*.md` (the author's pressure tests). Changed the `superpowers:` prefix on two skill references to plain names. `find-polluter.sh` assumes `npm test`; adapt it for pytest. |
| `test-driven-development` | obra/superpowers `skills/test-driven-development` | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | `writing-good-tests.md`: changed the `superpowers:writing-skills` reference to point at the upstream repo (that skill isn't copied). |
| `verification-before-completion` | obra/superpowers `skills/verification-before-completion` | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | None |
| `receiving-code-review` | obra/superpowers `skills/receiving-code-review` | `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` | None |
| `grilling` | [mattpocock/skills](https://github.com/mattpocock/skills) `skills/productivity/grilling` | `5beb35b040e3de97e54fa9e386d7e42d15c295c2` | Dropped `agents/` (Codex-only config) |
| `grill-me` | mattpocock/skills `skills/productivity/grill-me` | `5beb35b040e3de97e54fa9e386d7e42d15c295c2` | Dropped `agents/` (Codex-only config) |

To update a skill, copy it again from upstream at a newer commit, reapply the local changes, and update this table.

## obra/superpowers license

```
MIT License

Copyright (c) 2025 Jesse Vincent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## mattpocock/skills license

```
MIT License

Copyright (c) 2026 Matt Pocock

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
