from pathlib import Path
import importlib.util
import subprocess
import sys


DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1IcTfyW3enKSwN2SDnbIDwMxDmULDriEO?usp=drive_link"
DATASET_ROOT = Path("dataset")


def main():
    DATASET_ROOT.mkdir(parents=True, exist_ok=True)

    if importlib.util.find_spec("gdown") is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "gdown",
            "--folder",
            DRIVE_FOLDER_URL,
            "-O",
            str(DATASET_ROOT),
        ]
    )

    print(f"Downloaded dataset files into: {DATASET_ROOT.resolve()}")


if __name__ == "__main__":
    main()
