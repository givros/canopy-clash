"""Refresh or restore the encrypted Unreal source archives with GnuPG 2 and Python 3.11+."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
ARCHIVES = PROJECT / "SourceArchives"
INDEX = ARCHIVES / "index.json"
DEFAULT_KEY = Path.home() / ".codex" / "keys" / "canopy-clash" / "source-archives.key"
PART_SIZE = 80 * 1024 * 1024
MANIFEST = "archive-files.json"
ROOTS = (
    "ArtSource/AstraTemple/References",
    "Content/Fab",
    "Content/EditableCharacters",
    "Content/TempleTDM/Bots",
    "Content/TempleTDM/Animation",
    "Content/TempleTDM/Presentation",
    "Content/Characters",
    "Content/Weapons",
    "Content/FirstPerson",
    "Content/Variant_Shooter",
    "Content/LevelPrototyping",
    "Content/Input",
    "Content/__ExternalActors__/FirstPerson",
    "Content/__ExternalActors__/Variant_Shooter",
    "Content/__ExternalObjects__/FirstPerson",
    "Content/__ExternalObjects__/Variant_Shooter",
)


def digest(path):
    with path.open("rb") as data:
        return hashlib.file_digest(data, "sha256").hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def gpg(key, home, source, destination, decrypt=False):
    executable = shutil.which("gpg")
    if not executable and os.name == "nt":
        executable = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/gpg.exe"
    if not executable or not Path(executable).is_file():
        raise SystemExit("Install GnuPG 2 or Git for Windows.")
    command = [
        str(executable), "--homedir", home.as_posix(), "--no-options", "--batch", "--yes", "--no-autostart",
        "--no-symkey-cache", "--pinentry-mode", "loopback", "--passphrase-fd", "0",
        "--output", destination.as_posix(),
    ]
    if decrypt:
        command += ["--decrypt"]
    else:
        command += ["--symmetric", "--cipher-algo", "AES256", "--compress-algo", "none", "--s2k-count", "65011712"]
    command.append(source.as_posix())
    with key.open("rb") as secret:
        result = subprocess.run(command, stdin=secret, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError("GnuPG failed: " + result.stderr.decode(errors="replace").strip())


def part_paths(group):
    for part in group["parts"]:
        name = part["name"]
        if not name or Path(name).name != name or not name.endswith(".part"):
            raise ValueError("Invalid archive part name")
        yield part, ARCHIVES / name


def check_parts(group):
    for entry, path in part_paths(group):
        if not path.is_file() or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError(f"Missing or damaged archive part: {path.name}")


def inventory(root):
    directory = PROJECT / root
    items = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected source symlink: {path}")
        if path.is_file():
            name = path.relative_to(PROJECT).as_posix()
            items[name] = digest(path)
    if not items:
        raise ValueError(f"Missing or empty source directory: {root}")
    return items


def package_group(root, files, manifest, work, home, key):
    packed = work / "source.tar.gz"
    with tarfile.open(packed, "w:gz", compresslevel=1) as archive:
        info = tarfile.TarInfo(MANIFEST)
        info.size = len(manifest)
        archive.addfile(info, io.BytesIO(manifest))
        for name in files:
            archive.add(PROJECT / name, arcname=name, recursive=False)
    encrypted = work / "source.tar.gz.gpg"
    gpg(key, home, packed, encrypted)
    signature = hashlib.sha256(manifest).hexdigest()
    prefix = root.replace("/", "-").lower() + "-" + signature[:16]
    parts = []
    with encrypted.open("rb") as archive:
        while data := archive.read(PART_SIZE):
            name = f"{prefix}.gpg.{len(parts) + 1:03d}.part"
            # Make a whole encrypted part visible atomically.
            with tempfile.NamedTemporaryFile(dir=ARCHIVES, delete=False) as partial:
                partial.write(data)
                temporary = Path(partial.name)
            temporary.replace(ARCHIVES / name)
            parts.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"root": root, "files": len(files), "manifest_sha256": signature, "parts": parts}


def read_index():
    with INDEX.open(encoding="utf-8") as src:
        result = json.load(src)
    if result["version"] != 1 or [g["root"] for g in result["groups"]] != list(ROOTS):
        raise ValueError("Unsupported source archive index")
    return {g["root"]: g for g in result["groups"]}


def refresh(key, work, home):
    ARCHIVES.mkdir(exist_ok=True)
    old = read_index() if INDEX.is_file() else {}
    if old:
        smallest = min(old.values(), key=lambda g: sum(p["bytes"] for p in g["parts"]))
        decrypt_group(smallest, work, home, key)
    groups = []
    for root in ROOTS:
        files = inventory(root)
        manifest = json_bytes(files)
        group = old.get(root)
        if group and group["manifest_sha256"] == hashlib.sha256(manifest).hexdigest():
            check_parts(group)
        else:
            group = package_group(root, files, manifest, work, home, key)
        groups.append(group)
        print(f"{root}: {len(files)} source files, {len(group['parts'])} encrypted parts", flush=True)
    new_index = json_bytes({"version": 1, "groups": groups})
    with tempfile.NamedTemporaryFile(dir=ARCHIVES, delete=False) as temp:
        temp.write(new_index)
        pending = Path(temp.name)
    pending.replace(INDEX)
    referenced = {path for group in groups for _, path in part_paths(group)}
    for previous in old.values():
        for _, path in part_paths(previous):
            if path not in referenced:
                path.unlink(missing_ok=True)


def safe_relative(name, root):
    path = PurePosixPath(name)
    if (not path.is_relative_to(root) or path == PurePosixPath(root) or ".." in path.parts
            or "\\" in name or ":" in name or path.as_posix() != name):
        raise ValueError(f"Invalid archive member path: {name}")
    return path


def decrypt_group(group, work, home, key):
    check_parts(group)
    encrypted = work / "source.tar.gz.gpg"
    with encrypted.open("wb") as output:
        for _, part in part_paths(group):
            with part.open("rb") as src:
                shutil.copyfileobj(src, output)
    packed = work / "source.tar.gz"
    gpg(key, home, encrypted, packed, decrypt=True)
    return packed


def unpack(group, stage, work, home, key):
    packed = decrypt_group(group, work, home, key)
    with tarfile.open(packed, "r|gz") as archive:
        entries = iter(archive)
        first = next(entries)
        if first.name != MANIFEST or not first.isfile():
            raise ValueError("Missing source manifest")
        manifest = archive.extractfile(first).read()
        if hashlib.sha256(manifest).hexdigest() != group["manifest_sha256"]:
            raise ValueError("Source manifest verification failed")
        files = json.loads(manifest)
        if len(files) != group["files"]:
            raise ValueError("Source file count mismatch")
        pending = set(files)
        for item in entries:
            if not item.isfile() or item.name not in pending:
                raise ValueError(f"Unexpected archive member: {item.name}")
            destination = stage / safe_relative(item.name, group["root"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            if digest(destination) != files[item.name]:
                raise ValueError(f"Source hash mismatch: {item.name}")
            pending.remove(item.name)
        if pending:
            raise ValueError("Source files missing from archive")
    return files


def restore(key, work, home, destination):
    dest = destination.resolve()
    stage = work / "verified"
    verified = {}
    for group in read_index().values():
        verified.update(unpack(group, stage, work, home, key))
        print(f"Verified {group['root']} ({group['files']} files)", flush=True)
    missing = []
    for name, original_hash in verified.items():
        target = dest / name
        if target.resolve() != target:
            raise ValueError(f"Refusing to restore through a symlink: {target}")
        if target.exists():
            if not target.is_file() or digest(target) != original_hash:
                raise ValueError(f"Existing file differs: {target}")
        else:
            missing.append(name)
    for name in missing:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
            temporary = Path(tmp.name)
        try:
            shutil.copyfile(stage / name, temporary)
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"Verified {len(verified)} files; restored {len(missing)} to {dest}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("restore", "refresh"))
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--dest", type=Path, default=PROJECT, help="restore directory (default: project)")
    args = parser.parse_args()
    if not args.key.is_file() or args.key.resolve().is_relative_to(PROJECT):
        parser.error("Supply a local passphrase file stored outside the repository.")
    with tempfile.TemporaryDirectory(prefix="canopy-sources-") as temporary:
        work = Path(temporary)
        home = work / "gnupg"
        home.mkdir(mode=0o700)
        if args.action == "refresh":
            refresh(args.key, work, home)
        else:
            restore(args.key, work, home, args.dest)
