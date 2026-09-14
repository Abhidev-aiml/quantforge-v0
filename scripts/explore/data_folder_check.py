from pathlib import Path

from engine.data import load_csv


def test_folder(folder: str):

    files = sorted(
        Path(folder).glob("*_comma.csv")
    )

    print("\n" + "=" * 90)
    print(f"LOADER TEST: {folder}")
    print("=" * 90)

    for path in files:

        try:

            df = load_csv(path)

            print(
                f"✅ {path.name:35} "
                f"{len(df):8,} bars  "
                f"{df.index[0]} → {df.index[-1]}"
            )

        except Exception as e:

            print(
                f"❌ {path.name}: {e}"
            )


def main():

    test_folder(
        "data/raw/fourhours"
    )

    test_folder(
        "data/raw/onehours"
    )


if __name__ == "__main__":
    main()