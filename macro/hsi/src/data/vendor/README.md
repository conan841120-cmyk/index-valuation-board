# Reviewed Sina HSI decoder

`sina_hk_decode.js` is the exact UTF-8 value of the `hk_js_decode` Python
string literal in AkShare `akshare/stock/cons.py`, extracted without executing
the Python file. It was statically reviewed as arithmetic/bit-stream decoding
code on 2026-10-11. No executable code is fetched during refresh.

- Upstream commit: `8623219ee91a4c4ed8ffa983cdc0f5bb7db7a264`
- Source: https://github.com/akfamily/akshare/blob/8623219ee91a4c4ed8ffa983cdc0f5bb7db7a264/akshare/stock/cons.py
- SHA-256: `39a599c94dde4df1c2eb0882d4bff9560160cfd52ead0797cebb04b3122c2f52`
- Upstream repository license: MIT; exact notice retained in `LICENSE`.

The Node wrapper checks the bytes it executes against the reviewed digest.
Updates require reviewing a fixed upstream commit and changing this file,
the wrapper digest and this record together. The VM timeout limits work;
the VM is not a security boundary for untrusted executable code. Workflow
privilege separation is handled separately.
