# Installation

Requires Python 3.10 or later and about 200 MB of disk space.

```bash
pip install example-tool==2.4.1
example-tool --version
```

The installer does not modify system Python. In order to use a proxy, set `HTTPS_PROXY` before running `pip`. Configuration is read from `~/.config/example/config.toml`; if the file is absent, defaults are used.

You must not run the tool as root. Doing so will change the ownership of the cache directory and subsequent runs will fail.
