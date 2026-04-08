from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from nyuctf.challenge import CTFChallenge
from nyuctf.dataset import CTFDataset

from .base import BasePlatform
from ..result.models import Session, Target, ValidationResult

logger = logging.getLogger(__name__)


class NyuPlatform(BasePlatform):
    def __init__(self, split: str = "test", version: str | None = None):
        dataset_kwargs: dict[str, Any] = {"split": split}
        if version is not None:
            dataset_kwargs["version"] = version
        self.dataset = CTFDataset(**dataset_kwargs)
        self.basedir = self.dataset.basedir
        logger.info(
            "Initialized NYU platform split=%s version=%s basedir=%s",
            split,
            version,
            self.basedir,
        )

    def list_targets(self) -> list[Target]:
        targets = [self._to_target(challenge) for challenge in self.dataset.dataset.values()]
        logger.info("Listed %s NYU targets", len(targets))
        return targets

    def get_target(self, target_id: str) -> Target:
        challenge = self.dataset.get(target_id)
        target = self._to_target(challenge)
        logger.info("Loaded target id=%s name=%s", target.id, target.name)
        return target

    def prepare(self, target: Target) -> Session:
        logger.info("Preparing target id=%s", target.id)
        challenge_info = self.dataset.get(target.id)
        challenge = CTFChallenge(challenge_info, self.basedir)
        self._ensure_docker_network("ctfnet")
        challenge.start_challenge_container()
        logger.info(
            "Started challenge container for target id=%s server=%s port=%s",
            target.id,
            challenge.server_name,
            challenge.port,
        )
        tempdir = Path(tempfile.mkdtemp(prefix=f"aaagentbench-{target.id}-"))
        files_dir = tempdir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        copied_files = self._copy_files(challenge, files_dir)
        logger.info(
            "Prepared temp workspace for target id=%s workdir=%s copied_files=%s",
            target.id,
            tempdir,
            len(copied_files),
        )
        session_target = Target(
            id=target.id,
            name=target.name,
            description=target.description,
            files=copied_files,
            flag_format=target.flag_format,
            metadata=dict(target.metadata),
        )

        execution_mode = "docker" if challenge.port else "static"
        solver_host = "host.docker.internal" if challenge.port else None
        target_url = None
        if challenge.port:
            scheme = "https" if "https" in (challenge.server_type or "").lower() else "http"
            target_url = f"{scheme}://{solver_host}:{challenge.port}"

        connection_info = {
            "server_name": "localhost" if challenge.server_name else None,
            "port": challenge.port,
            "server_type": challenge.server_type,
            "execution_mode": execution_mode,
            "solver_host": solver_host,
            "target_url": target_url,
        }

        return Session(
            target=session_target,
            connection_info=connection_info,
            workdir=str(tempdir),
            metadata={
                "challenge": challenge,
                "flag": challenge.flag,
                "container": challenge.container,
                "tempdir": str(tempdir),
            },
        )

    def validate_flag(self, session: Session, flag: str) -> ValidationResult:
        expected_flag = session.metadata["flag"]
        if flag == expected_flag:
            logger.info("Flag validated successfully for target id=%s", session.target.id)
            return ValidationResult(ok=True, message="Correct flag")
        logger.warning("Flag validation failed for target id=%s", session.target.id)
        return ValidationResult(ok=False, message="Incorrect flag")

    def cleanup(self, session: Session) -> None:
        logger.info("Cleaning up target id=%s", session.target.id)
        challenge = session.metadata.get("challenge")
        if challenge is not None:
            challenge.stop_challenge_container()
            logger.info("Stopped challenge container for target id=%s", session.target.id)
        tempdir = session.metadata.get("tempdir")
        if tempdir:
            shutil.rmtree(tempdir, ignore_errors=True)
            logger.info("Removed temp workspace for target id=%s workdir=%s", session.target.id, tempdir)

    def _to_target(self, challenge_info: dict[str, Any]) -> Target:
        challenge = CTFChallenge(challenge_info, self.basedir)
        files = [str(Path(challenge.challenge_dir) / file_name) for file_name in challenge.files]
        description = self._rewrite_server_name(challenge.description, challenge.server_name)

        return Target(
            id=challenge.canonical_name,
            name=challenge.name,
            description=description,
            files=files,
            flag_format=challenge.flag_format,
            metadata={
                "year": challenge.year,
                "event": challenge.event,
                "category": challenge.category,
                "container": challenge.container,
                "server_name": "localhost" if challenge.server_name else None,
                "original_server_name": challenge.server_name,
                "port": challenge.port,
                "challenge_path": str(challenge.challenge_dir),
            },
        )

    @staticmethod
    def _rewrite_server_name(description: str, server_name: str | None) -> str:
        if not server_name:
            return description
        return description.replace(server_name, "localhost")

    @staticmethod
    def _ensure_docker_network(network_name: str) -> None:
        inspect = subprocess.run(
            ["docker", "network", "inspect", network_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if inspect.returncode == 0:
            return

        logger.info("Creating docker network %s for NYU challenge containers", network_name)
        create = subprocess.run(
            ["docker", "network", "create", network_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if create.returncode != 0:
            raise RuntimeError(
                f"Failed to create docker network {network_name}: "
                f"{create.stderr.strip() or create.stdout.strip()}"
            )

    @staticmethod
    def _copy_files(challenge: CTFChallenge, destination_dir: Path) -> list[str]:
        copied_files: list[str] = []
        for file_name in challenge.files:
            source = Path(challenge.challenge_dir) / file_name
            relative_path = Path(file_name)
            destination = destination_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("Copying challenge file source=%s destination=%s", source, destination)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
            copied_files.append(str(destination))
        return copied_files
