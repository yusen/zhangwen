# ZW-MPY-SIM third-party notices

The native host-core contract is pinned to MicroPython v1.26.1, upstream commit
`647c8b96cae7e202c7a020395b7cfe65e5b8ce04`, under the MIT license. The official
source archive SHA-256 is recorded in `runtime-manifest.json`.

No upstream MicroPython binary is bundled in this milestone. A future native distribution must
be built from the pinned source and Zhangwen host patch revision, receive a platform-specific
SHA-256 entry in the immutable manifest, and carry all licenses of the source files actually
included by that build. Until then the native engine fails closed.

The restricted CPython behavioral reference is Zhangwen implementation code. It is explicitly
not MicroPython and is not eligible to create native-MicroPython or project Evidence.
