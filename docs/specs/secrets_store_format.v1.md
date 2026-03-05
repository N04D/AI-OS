# Secrets Store Format v1

- File path: `~/.local/share/aios/secrets/store.v1`
- Magic header: `AIOSSEC1`
- Version: `1`
- Header encoding: JSON with `version`, `kdf`, `salt`, `nonce`, `meta`
- Cipher: `AES-256-GCM`
- Payload: encrypted JSON map of key -> base64 value
- AAD binding: version + hostname + uid
- Write semantics: atomic temp write + fsync + rename
- Permissions: `0600`

Contract notes:
- Header magic and version are frozen for v1 readers.
- Any incompatible changes require `store.v2`.
