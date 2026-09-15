from backend.app.policy.linter import lint


def test_forbidden_remove_item():
    r = lint('Remove-Item -Path "C:\\" -Recurse -Force')
    assert r["passed"] is False
    assert r["blocked_token"] == "remove-item"


def test_allowlisted_cmdlet():
    r = lint("Write-Output 'scan complete'\nGet-FileHash C:\\restore.log")
    assert r["passed"] is True


def test_certified_isolate_restore_script():
    r = lint("Isolate-Endpoint -Id $host\nGet-Backup -Host $host\nRestore-Backup -SnapshotId $clean")
    assert r["passed"] is True
