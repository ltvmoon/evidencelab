"""Unit tests for ``_validate_dump_archive`` in scripts/sync/db/dump_postgres.py.

The function copies a dump into the postgres container, runs ``pg_restore -l``
against it, and cleans up — even on failure. Tests stub ``subprocess.run`` so
they execute without a real docker compose stack.
"""

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "sync" / "db" / "dump_postgres.py"
)
_spec = importlib.util.spec_from_file_location("dump_postgres", _SCRIPT_PATH)
dump_postgres = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dump_postgres)


def _ok(_returncode: int = 0):
    """Helper: build a CompletedProcess that succeeded."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _fail(stderr: str = "boom"):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


@pytest.mark.unit
class TestValidateDumpArchive:
    def test_passes_when_copy_and_pg_restore_both_succeed(self, tmp_path):
        dump = tmp_path / "postgres.dump"
        dump.write_bytes(b"placeholder")

        with patch.object(dump_postgres.subprocess, "run") as run:
            run.side_effect = [_ok(), _ok(), _ok()]  # copy, pg_restore -l, cleanup
            dump_postgres._validate_dump_archive(
                root_dir=tmp_path, use_prod=False, dump_path=dump
            )
        assert run.call_count == 3

    def test_uses_data_dir_scratch_path_not_tmp(self, tmp_path):
        """Bandit B108 flags /tmp/ paths even inside containers; the
        validator must use a writable non-tmp path so the public repo
        doesn't carry a # nosec suppression."""
        dump = tmp_path / "postgres.dump"
        dump.write_bytes(b"placeholder")
        with patch.object(dump_postgres.subprocess, "run") as run:
            run.side_effect = [_ok(), _ok(), _ok()]
            dump_postgres._validate_dump_archive(
                root_dir=tmp_path, use_prod=False, dump_path=dump
            )
        # First call is the docker compose cp; assert the IN-CONTAINER
        # destination is the data dir, not /tmp/. The host source path
        # may legitimately be /tmp/* (pytest's tmp_path), so we only
        # check the part after the ``postgres:`` container prefix.
        first_cmd = run.call_args_list[0].args[0]
        assert "/var/lib/postgresql/data/_dump_validate_postgres.dump" in first_cmd
        container_dest = first_cmd.split("postgres:", 1)[1]
        assert not container_dest.startswith("/tmp/")

    def test_raises_when_copy_into_container_fails(self, tmp_path):
        dump = tmp_path / "postgres.dump"
        dump.write_bytes(b"placeholder")
        with patch.object(dump_postgres.subprocess, "run") as run:
            run.side_effect = [_fail("docker daemon down")]
            with pytest.raises(
                RuntimeError, match="could not copy dump into container"
            ):
                dump_postgres._validate_dump_archive(
                    root_dir=tmp_path, use_prod=False, dump_path=dump
                )

    def test_raises_when_pg_restore_rejects_archive(self, tmp_path):
        dump = tmp_path / "postgres.dump"
        dump.write_bytes(b"placeholder")
        with patch.object(dump_postgres.subprocess, "run") as run:
            run.side_effect = [
                _ok(),  # copy
                _fail("pg_restore: [archiver] unexpected end of file"),
                _ok(),  # cleanup still runs in finally
            ]
            with pytest.raises(RuntimeError, match="pg_restore could not read"):
                dump_postgres._validate_dump_archive(
                    root_dir=tmp_path, use_prod=False, dump_path=dump
                )
        # Cleanup MUST run even on validation failure — three calls total.
        assert run.call_count == 3
        cleanup_cmd = run.call_args_list[2].args[0]
        assert "rm -f" in cleanup_cmd
        assert "_dump_validate_postgres.dump" in cleanup_cmd

    def test_cleanup_runs_even_when_pg_restore_raises(self, tmp_path):
        """An exception during the pg_restore subprocess (not a non-zero
        exit) still needs the cleanup step to fire — the finally block
        must always run."""
        dump = tmp_path / "postgres.dump"
        dump.write_bytes(b"placeholder")
        calls = []

        def fake_run(cmd, *_args, **_kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                return _ok()  # copy
            if len(calls) == 2:
                raise OSError("pg_restore went sideways")
            return _ok()  # cleanup

        with patch.object(dump_postgres.subprocess, "run", side_effect=fake_run):
            with pytest.raises(OSError, match="pg_restore went sideways"):
                dump_postgres._validate_dump_archive(
                    root_dir=tmp_path, use_prod=False, dump_path=dump
                )
        assert len(calls) == 3
        assert "rm -f" in calls[2]
