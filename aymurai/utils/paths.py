from pathlib import Path

TEST_SUFFIX = "-test"


def test_id_from_filename(test_path: Path, *, test_suffix: str = TEST_SUFFIX) -> str:
    """
    Convert a test filename like "document-1-test.json" into "document-1".
    Falls back to stripping ".json" when the suffix is not present.

    Args:
        test_path (Path): Path to the test file.
        test_suffix (str, optional): Suffix indicating test files. Defaults to "-test".

    Returns:
        str: The test identifier extracted from the filename.
    """
    name = Path(test_path).name
    suffix_with_ext = f"{test_suffix}.json"
    if name.endswith(suffix_with_ext):
        return name[: -len(suffix_with_ext)]
    if name.endswith(".json"):
        return name[: -len(".json")]
    return name


def prediction_filename_for_test(
    test_path: Path, *, test_suffix: str = TEST_SUFFIX
) -> str:
    """
    Return the prediction filename that should correspond to the test file.

    Args:
        test_path (Path): Path to the test file.
        test_suffix (str, optional): Suffix indicating test files. Defaults to "-test".

    Returns:
        str: The prediction filename corresponding to the test file.
    """
    return f"{test_id_from_filename(test_path, test_suffix=test_suffix)}.json"
