"""Download one matched frame from the public CarlaSC Cartesian test archive."""

import argparse
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen


ARCHIVE_URL = "https://curly-dataset-public.s3.us-east-2.amazonaws.com/CARLA/test_cartesian.zip"


class RemoteZipReader(io.RawIOBase):
    def __init__(self):
        super().__init__()
        self.position = 0
        request = Request(ARCHIVE_URL, headers={"Range": "bytes=0-0"})
        with urlopen(request, timeout=40) as response:
            span = response.headers.get("Content-Range", "")
            if response.status != 206 or not span.startswith("bytes 0-0/"):
                raise OSError(f"Archive server did not honor the range request: {span}")
            self.size = int(span.split("/")[-1])
            self.etag = response.headers.get("ETag")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        position = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}[whence] + offset
        if position < 0:
            raise OSError("Cannot seek before the start of the archive.")
        self.position = position
        return position

    def read(self, size=-1):
        remaining = max(0, self.size - self.position)
        size = remaining if size is None or size < 0 else min(size, remaining)
        if size == 0:
            return b""
        if size > 64 * 1024 * 1024:
            raise OSError("Refusing to download an unexpectedly large archive segment.")

        start, end = self.position, self.position + size - 1
        headers = {"Range": f"bytes={start}-{end}"}
        if self.etag:
            headers["If-Match"] = self.etag
        request = Request(ARCHIVE_URL, headers=headers)
        with urlopen(request, timeout=60) as response:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{self.size}":
                raise OSError(f"Unexpected archive range response for bytes {start}-{end}.")
            data = response.read(size + 1)
        if len(data) != size:
            raise OSError(f"Received {len(data)} bytes when {size} were requested.")
        self.position += size
        return data


def frame_files(scene, frame):
    return {
        "velodyne.bin": f"{scene}/velodyne/{frame}.bin",
        "ground_truth.label": f"{scene}/evaluation/{frame}.label",
        "eval_counts.bin": f"{scene}/evaluation/{frame}.bin",
        "params.json": f"{scene}/evaluation/params.json",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory for the selected frame")
    parser.add_argument("--sample", help="Sequence and six-digit frame, such as Town10_Heavy/000600")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("--output must be a new directory")
    if args.sample and not re.fullmatch(r"Town\d+_(Heavy|Medium|Light)/\d{6}", args.sample):
        parser.error("--sample must use the format Town10_Heavy/000600")

    with RemoteZipReader() as reader, zipfile.ZipFile(reader) as archive:
        members = set(archive.namelist())
        if args.sample:
            sequence, frame = args.sample.split("/")
            scene = f"Cartesian/Test/{sequence}/cartesian"
            files = frame_files(scene, frame)
            missing = set(files.values()) - members
            if missing:
                raise FileNotFoundError(f"Missing archive members: {', '.join(sorted(missing))}")
        else:
            for scan in sorted(name for name in members if "/cartesian/velodyne/" in name and name.endswith(".bin")):
                scene, basename = scan.rsplit("/velodyne/", 1)
                frame = Path(basename).stem
                files = frame_files(scene, frame)
                if members.issuperset(files.values()):
                    break
            else:
                raise RuntimeError("No matched Cartesian test frame was found in the archive.")

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output.parent) as temp:
            staging = Path(temp) / "frame"
            staging.mkdir()
            for local_name, member in files.items():
                print(f"Reading {member}", flush=True)
                # ZipFile.read checks each member's CRC32 as it decompresses it.
                (staging / local_name).write_bytes(archive.read(member))
            metadata = {"archive_url": ARCHIVE_URL, "archive_members": files, "scene": scene, "frame": frame}
            (staging / "frame.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            staging.rename(output)
    print(f"Saved matched scan, ground truth, and evaluation counts to {output}")


if __name__ == "__main__":
    main()
