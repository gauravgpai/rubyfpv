#!/usr/bin/env python3
"""Make a Ruby controller USB update from the official ruby_update_11.8.zip.

    make-update-zip.py OFFICIAL.zip BUILD_DIR OUT.zip

Every entry of the official archive is copied unchanged (camera binaries,
plugins, SDL libs, resources, ruby_update.log), except bin/radxaz3/ruby_*
binaries that also exist in BUILD_DIR: those are replaced with the patched
build. Nothing is added that the official archive does not already have.
Standard library only; runs on the Radxa (python3) and on a PC.
"""
import hashlib
import os
import sys
import zipfile

OFFICIAL_SHA256 = "21fa13b9a2f3b51f501d17c609c58257c7944b30dc445a70b3a9eaa71fe4f4d2"
RADXA = "bin/radxaz3/"
ELF_AARCH64 = (b"\x7fELF\x02\x01", 183)  # 64-bit LE, e_machine EM_AARCH64


def is_aarch64_elf(data):
    return data[:6] == ELF_AARCH64[0] and int.from_bytes(data[18:20], "little") == ELF_AARCH64[1]


def main(official, build_dir, out):
    with open(official, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != OFFICIAL_SHA256:
        sys.exit(f"{official}: sha256 {digest} is not the official ruby_update_11.8.zip")

    replaced, kept = [], []
    with zipfile.ZipFile(official) as zin, zipfile.ZipFile(out + ".tmp", "w") as zout:
        for info in zin.infolist():
            data = zin.read(info)
            name = info.filename
            base = name[len(RADXA):]
            if name.startswith(RADXA) and base.startswith("ruby_") and "/" not in base:
                built = os.path.join(build_dir, base)
                if os.path.isfile(built):
                    with open(built, "rb") as f:
                        new = f.read()
                    if not is_aarch64_elf(data):
                        kept.append(base)          # e.g. .uf2 firmware: never replaced
                    elif not is_aarch64_elf(new):
                        sys.exit(f"{built}: not an aarch64 ELF binary")
                    else:
                        data = new
                        replaced.append(base)
                elif is_aarch64_elf(data):
                    kept.append(base)
            zout.writestr(info, data, compress_type=info.compress_type)

    if "ruby_start" not in replaced or "ruby_central" not in replaced:
        os.remove(out + ".tmp")
        sys.exit("ruby_start / ruby_central missing from the build; archive not written")
    os.replace(out + ".tmp", out)
    print(f"replaced {len(replaced)}: {' '.join(sorted(replaced))}")
    if kept:
        print(f"kept stock {len(kept)}: {' '.join(sorted(kept))}")
    with open(out, "rb") as f:
        print(f"{out}  sha256 {hashlib.sha256(f.read()).hexdigest()}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    try:
        main(*sys.argv[1:])
    finally:
        if os.path.exists(sys.argv[3] + ".tmp"):
            os.remove(sys.argv[3] + ".tmp")
