"""Pack byte-identical IoStore blocks once while preserving the original file offsets."""

import hashlib
import os
import struct
import tempfile
from contextlib import ExitStack
from pathlib import Path


PIECE_SIZE = 16 * 1024 * 1024


def _block_starts(container, size):
    toc = container.with_suffix(".utoc").read_bytes()
    if len(toc) < 100 or toc[:16] != b"-==--==--==--==-" or not 8 <= toc[16] <= 11:
        raise ValueError(f"Unsupported IoStore table for {container}")
    header_size, entry_count, block_count, block_stride = struct.unpack_from("<4I", toc, 20)
    partitions = struct.unpack_from("<I", toc, 52)[0]
    seed_count = struct.unpack_from("<I", toc, 84)[0]
    overflow_count = struct.unpack_from("<I", toc, 96)[0]
    # Each chunk has a 12-byte ID and a 10-byte logical offset/length pair.
    table = header_size + 22 * entry_count + 4 * (seed_count + overflow_count)
    if (partitions != 1 or block_stride != 12 or header_size < 100
            or table + block_count * block_stride > len(toc)):
        raise ValueError(f"Invalid or partitioned IoStore table for {container}")

    blocks = []
    for pos in range(table, table + block_count * block_stride, block_stride):
        offset = int.from_bytes(toc[pos:pos + 5], "little")
        length = int.from_bytes(toc[pos + 5:pos + 8], "little")
        blocks.append((offset, length))
    starts = [0]
    previous_end = 0
    for offset, length in sorted(blocks):
        if length == 0 or offset < previous_end or offset + length > size:
            raise ValueError(f"Invalid physical IoStore block at {offset} in {container}")
        if starts[-1] != offset:
            starts.append(offset)
        previous_end = offset + length
    if starts[-1] != size:
        starts.append(size)
    return starts


def _store_piece(data, output):
    name = f"blobs/{hashlib.sha256(data).hexdigest()}.bin"
    target = output / name
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return name


def verify_container(ucas_path, output_dir, layout):
    """Compare every byte reconstructed from the published ranges with the source."""
    container = Path(ucas_path)
    size = container.stat().st_size
    segments = layout["segments"]
    if layout["size"] != size or (size and (not segments or segments[0][0] != 0)):
        raise ValueError(f"Invalid coverage for {container}")
    with container.open("rb") as source, ExitStack() as handles:
        pieces = [handles.enter_context((Path(output_dir) / piece).open("rb"))
                  for piece in layout["pieces"]]
        for index, (start, piece, offset) in enumerate(segments):
            end = segments[index + 1][0] if index + 1 < len(segments) else size
            if end <= start or end > size or not 0 <= piece < len(pieces) or offset < 0:
                raise ValueError(f"Invalid published segment at {start} in {container}")
            packed = pieces[piece]
            packed.seek(offset)
            remaining = end - start
            while remaining:
                length = min(remaining, 1024 * 1024)
                data = packed.read(length)
                if len(data) != length or data != source.read(length):
                    raise ValueError(f"Published bytes differ at {end - remaining} in {container}")
                remaining -= length


def pack_container(ucas_path, output_dir, shared_blocks=None, shared_pieces=None):
    """Write content-addressed pieces and return their logical-to-physical range map."""
    container = Path(ucas_path)
    output = Path(output_dir)
    (output / "blobs").mkdir(parents=True, exist_ok=True)
    size = container.stat().st_size
    starts = _block_starts(container, size)
    # A second cook has different offsets, but often contains exactly the
    # same meshes, animations and audio blocks. Keep one physical copy.
    pieces = [] if shared_pieces is None else shared_pieces
    segments = []
    stored = {} if shared_blocks is None else shared_blocks
    pending = bytearray()
    with container.open("rb") as source:
        for start, end in zip(starts, starts[1:]):
            # Include alignment padding in each interval so arbitrary byte ranges match.
            for logical in range(start, end, PIECE_SIZE):
                length = min(PIECE_SIZE, end - logical)
                block = source.read(length)
                if len(block) != length:
                    raise ValueError(f"Truncated IoStore container at {logical} in {container}")
                digest = hashlib.sha256(block).digest()
                if digest not in stored:
                    if pending and len(pending) + length > PIECE_SIZE:
                        pieces.append(_store_piece(pending, output))
                        pending.clear()
                    stored[digest] = (len(pieces), len(pending))
                    pending.extend(block)
                piece, offset = stored[digest]
                if segments:
                    last_start, last_piece, last_offset = segments[-1]
                    if piece == last_piece and offset == last_offset + logical - last_start:
                        continue
                segments.append([logical, piece, offset])
    if pending:
        pieces.append(_store_piece(pending, output))
    used = sorted({segment[1] for segment in segments})
    remap = {shared: local for local, shared in enumerate(used)}
    for segment in segments:
        segment[1] = remap[segment[1]]
    layout = {"size": size, "pieces": [pieces[i] for i in used], "segments": segments}
    verify_container(container, output, layout)
    return layout
