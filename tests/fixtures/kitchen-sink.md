# Kitchen Sink

A document exercising every supported Markdown feature so each template can be
visually inspected end-to-end. Edit and re-render to iterate on styles.

## Inline formatting

Plain text. **Bold text**, *italic text*, ***bold italic***, ~~strikethrough~~,
`inline code`, and a [link to example](https://example.com). Hard linebreak\
follows. Autolink: https://example.com.

A literal subscript-ish ^thing^ stays as-is. A keyboard shortcut: <kbd>Ctrl</kbd>+<kbd>C</kbd>.

## Headings

### Heading level three

#### Heading level four

##### Heading level five

###### Heading level six

## Paragraphs and quotes

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.

> A single-line blockquote.

> A blockquote with **inline formatting** and `code`.
>
> Spanning multiple paragraphs and even containing a nested quote:
>
> > Nested quotes work too — useful for "they said" / "I said" exchanges.

## Lists

Unordered:

- First item
- Second item
  - Nested item
  - Another nested item
    - Even deeper
- Third item

Ordered:

1. Step one
2. Step two
   1. Sub-step a
   2. Sub-step b
3. Step three

Task list:

- [x] Done item
- [x] Another completed item
- [ ] Pending item
- [ ] Yet to do

## Definition list

Markdown
: A lightweight markup language for plain-text formatting.

HTML
: The standard markup language for documents designed to be displayed in a
  web browser.

CSS
: A style sheet language used for describing the presentation of a document
  written in a markup language.

## Code

Inline code: `const x = 42`.

Python:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Greeting:
    """Generate a friendly greeting."""
    recipient: str

    def render(self) -> str:
        return f"Hello, {self.recipient}!"


if __name__ == "__main__":
    print(Greeting("world").render())
```

JavaScript:

```javascript
// A simple async function
async function fetchUser(id) {
  const res = await fetch(`/api/users/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const users = await Promise.all([1, 2, 3].map(fetchUser));
console.log(users);
```

Rust:

```rust
use std::collections::HashMap;

fn count_words(text: &str) -> HashMap<String, usize> {
    let mut counts = HashMap::new();
    for word in text.split_whitespace() {
        *counts.entry(word.to_lowercase()).or_insert(0) += 1;
    }
    counts
}

fn main() {
    let counts = count_words("hello world hello");
    println!("{:?}", counts);
}
```

Shell:

```bash
#!/usr/bin/env bash
set -euo pipefail

for file in *.md; do
  echo "Converting ${file}..."
  md2html "${file}" -t github
done
```

JSON:

```json
{
  "name": "md2html",
  "version": "0.1.0",
  "templates": ["minimal-light", "minimal-dark", "github", "polished"],
  "features": {
    "tables": true,
    "footnotes": true,
    "tasklists": true
  }
}
```

Code with no language hint:

```
This block has no language. It should render as preformatted text without
syntax highlighting but still inside the same styled container.
```

## Tables

| Template       | Background  | Best for                  | Stars |
| -------------- | ----------- | ------------------------- | ----: |
| `minimal-light`| white       | reading-focused docs      |   ★★★ |
| `minimal-dark` | near-black  | nighttime / OLED screens  |  ★★★★ |
| `basic-light`  | white       | structured documentation  |   ★★★ |
| `basic-dark`   | dark slate  | docs with lots of code    |  ★★★★ |
| `github`       | adapts      | README-style content      | ★★★★★ |
| `polished`     | warm cream  | long-form essays, reports |  ★★★★ |

## Horizontal rule

Content above.

---

Content below.

## Images

![A placeholder logo](sample.png)

## Footnotes

Markdown supports footnotes[^1] for inline citations, with longer notes[^longnote]
that can hold multiple lines.

[^1]: This is the first footnote.

[^longnote]: This footnote has multiple paragraphs.

    Continuation paragraphs are indented under the marker.

## HTML

Inline HTML is preserved:

<details>
<summary>Click to expand</summary>

Hidden content with **bold** inside.

</details>

## Long line stress test

Pneumonoultramicroscopicsilicovolcanoconiosis is a long word that should wrap or scroll inside narrow code blocks without breaking the layout — `Pneumonoultramicroscopicsilicovolcanoconiosis-is-a-long-word-that-should-wrap`.

That's a wrap.
