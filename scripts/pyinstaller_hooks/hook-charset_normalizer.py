try:
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore[no-redef]


def _find_mypyc_hiddenimports(dist_name: str) -> list[str]:
    try:
        dist = importlib_metadata.distribution(dist_name)
    except importlib_metadata.PackageNotFoundError:
        return []
    return sorted({entry.name.split(".")[0] for entry in (dist.files or []) if "__mypyc" in entry.name})


hiddenimports = _find_mypyc_hiddenimports("charset-normalizer")
