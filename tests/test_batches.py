from agents.orchestrator import batches


def test_batches_respect_limit(tmp_path):
    files = []
    for i, n in enumerate([10, 20, 35, 5, 70, 5]):
        p = tmp_path / f"{i:03d}.txt"
        p.write_text("x" * n, encoding="utf-8")
        files.append(p)
    b = batches(files, limit=50)
    assert [[p.name for p, _ in grp] for grp in b] == [["000.txt", "001.txt"], ["002.txt", "003.txt"],
                                                       ["004.txt"], ["005.txt"]]
    assert batches([], limit=50) == []
