# statcode

> [!NOTE]
> Thanks to [@shobrook](https://github.com/shobrook) for the original project and inspiration.
> The [`statcode` AUR package](https://aur.archlinux.org/packages/statcode) is orphaned and no longer maintained. The package no longer work as expected.

`statcode` is like `man` but for HTTP status codes. If you're a web developer, you probably spend some time looking at response codes (usually errors) and then Googling what they mean. But with `statcode`, you can simply run `$ statcode [status_code]` and get a quick explanation of your HTTP response without leaving the terminal.

![demo](assets/demo.gif)

## Installation

>Requires Python 3.0 or higher

`statcode` works on macOS, Linux, and Windows. You can install it using [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install statcode
```
