from utils.diagnostics import PacketLog, packet_log_path


def test_each_packet_is_one_line_with_direction_and_hex(tmp_path):
    log = PacketLog(tmp_path / "p.log")
    log.write("tx", bytes.fromhex("fedcba04"))
    log.write("rx", b"\x01\x02")

    lines = (tmp_path / "p.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].split()[1:] == ["tx", "fedcba04"]
    assert lines[1].split()[1:] == ["rx", "0102"]


def test_log_is_rotated_instead_of_growing_forever(tmp_path):
    path = tmp_path / "p.log"
    log = PacketLog(path, max_bytes=200)
    for _ in range(50):
        log.write("rx", b"\xaa" * 20)

    assert path.stat().st_size <= 200 + 100
    assert (tmp_path / "p.log.1").exists()


def test_write_never_raises_when_the_folder_is_gone(tmp_path):
    log = PacketLog(tmp_path / "missing" / "p.log")
    log.write("tx", b"\x00")


def test_path_is_per_device_and_safe_for_the_filesystem(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = packet_log_path("Redmi Buds 5 Pro/../x")
    assert path.parent == tmp_path / "MiBudsClient"
    assert path.name == "packets-redmi-buds-5-pro-x.log"
