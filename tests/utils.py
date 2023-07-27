from copy import copy


def mktree(lp, d):
    """
    Create a tree of files from a dictionary of name > content lookups.
    """
    for name, content in d.items():
        _lp = copy(lp)

        parts = list(filter(bool, name.split('/')))
        for part in parts[:-1]:
            _lp = _lp.mkdir(part)
        _lp = _lp.join(parts[-1])

        if isinstance(content, dict):
            _lp.mkdir()
            mktree(_lp, content)
        else:
            _lp.write(content)


def gettree(lp, max_len=120):
    """
    Get a dict representing the file tree for a directory
    """
    assert lp.check()
    if lp.isdir():
        return {df.basename: gettree(df, max_len=max_len) for df in lp.listdir()}
    else:
        assert lp.isfile()
        content = lp.read_text('utf8')
        if max_len and len(content) > max_len:
            content = content[: max_len - 3] + '...'
        return content
