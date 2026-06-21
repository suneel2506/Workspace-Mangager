"""
============================================================
  file_manager.py -- Filesystem Automation
============================================================

PURPOSE:
    Provides safe, logged wrappers around common filesystem
    operations: creating folders, deleting them, moving files,
    listing directory contents, and the headline feature --
    automatically organising the user's Downloads folder by
    file type.

HOW ``organize_downloads()`` WORKS:
    1.  Iterate every *file* (not subdirectory) in DOWNLOADS_DIR.
    2.  Look up the file's extension in FILE_CATEGORIES to find
        the target category folder (e.g. ".pdf" -> "Documents").
    3.  Create the category subfolder if it doesn't exist.
    4.  Move the file into that subfolder.
    5.  Files whose extension is not in FILE_CATEGORIES are placed
        into a catch-all "Other" folder.
    6.  Return a summary dict  {category: count_moved}.

DESIGN NOTES:
    * ``shutil.move`` is used instead of ``Path.rename`` because
      ``rename`` fails when source and destination are on
      different drives (Windows) or filesystems (Linux).
    * Destructive operations (``delete_folder``) require an
      explicit CLI confirmation via ``input()``.
    * Every action is logged through the standard
      ``Workspace Automation System`` logger.

FUTURE HOOKS:
    * Dry-run / preview mode for organize_downloads.
    * Undo support (record moves so they can be reversed).
    * Configurable category overrides from a user YAML file.
    * Scheduled auto-organisation via Windows Task Scheduler.
============================================================
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from config.settings import DOWNLOADS_DIR, FILE_CATEGORIES, get_category_for_extension


# ── Module-level logger ────────────────────────────────────
logger: logging.Logger = logging.getLogger("Workspace Automation System")


class FileManager:
    """
    Safe, logged filesystem operations for the Workspace
    Automation System.

    Usage
    -----
        fm = FileManager()
        fm.create_folder("C:/Projects/new_project")
        fm.organize_downloads()
        fm.move_file("C:/old/report.pdf", "C:/new/report.pdf")
    """

    # ── Public API ─────────────────────────────────────────

    def create_folder(self, path: str) -> bool:
        """
        Create a directory, including any missing parents.

        Behaves like ``mkdir -p`` -- it is safe to call even if
        the directory already exists.

        Parameters
        ----------
        path : str
            Absolute or relative path to the directory to create.

        Returns
        -------
        bool
            ``True`` if the directory now exists (created or was
            already present), ``False`` on error.

        Examples
        --------
        >>> FileManager().create_folder("C:/Projects/demo")
        True
        """
        if not path or not path.strip():
            logger.error("create_folder() called with an empty path.")
            return False

        target: Path = Path(path).resolve()

        try:
            # ``exist_ok=True`` means "don't fail if it already exists".
            target.mkdir(parents=True, exist_ok=True)
            logger.info("Folder created (or already exists): %s", target)
            return True

        except PermissionError:
            logger.error("Permission denied when creating folder: %s", target)
            return False

        except OSError as exc:
            logger.error("Failed to create folder '%s': %s", target, exc)
            return False

    def delete_folder(self, path: str) -> bool:
        """
        Delete a directory and **all** of its contents.

        A CLI confirmation prompt is shown before the deletion
        proceeds.  The user must type ``y`` or ``yes`` to confirm.

        Parameters
        ----------
        path : str
            Path to the directory to delete.

        Returns
        -------
        bool
            ``True`` if the directory was deleted, ``False`` if the
            user cancelled, the path was invalid, or an error
            occurred.

        Examples
        --------
        >>> FileManager().delete_folder("C:/Projects/old_project")
        Delete folder and ALL contents? C:/Projects/old_project [y/N]: y
        True
        """
        if not path or not path.strip():
            logger.error("delete_folder() called with an empty path.")
            return False

        target: Path = Path(path).resolve()

        # Guard: does the directory actually exist?
        if not target.exists():
            logger.warning("delete_folder(): path does not exist: %s", target)
            return False

        if not target.is_dir():
            logger.error("delete_folder(): path is not a directory: %s", target)
            return False

        # ── Confirmation prompt (safety net) ───────────────
        try:
            answer: str = input(
                f"  Delete folder and ALL contents? {target} [y/N]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Non-interactive context or user pressed Ctrl+C.
            logger.info("Deletion cancelled (no interactive input).")
            return False

        if answer not in ("y", "yes"):
            logger.info("Deletion cancelled by user: %s", target)
            return False

        # ── Perform the deletion ───────────────────────────
        try:
            shutil.rmtree(target)
            logger.info("Folder deleted: %s", target)
            return True

        except PermissionError:
            logger.error("Permission denied when deleting folder: %s", target)
            return False

        except OSError as exc:
            logger.error("Failed to delete folder '%s': %s", target, exc)
            return False

    def move_file(self, source: str, destination: str) -> bool:
        """
        Move a file or folder from *source* to *destination*.

        Uses ``shutil.move`` which works across drives / mount
        points (unlike ``Path.rename``).

        Parameters
        ----------
        source : str
            Current path of the file or directory.
        destination : str
            Target path (may be a directory or a full filename).

        Returns
        -------
        bool
            ``True`` if the move succeeded, ``False`` otherwise.

        Examples
        --------
        >>> FileManager().move_file("C:/old/report.pdf", "C:/new/report.pdf")
        True
        """
        if not source or not source.strip():
            logger.error("move_file(): empty source path.")
            return False

        if not destination or not destination.strip():
            logger.error("move_file(): empty destination path.")
            return False

        src: Path = Path(source).resolve()
        dst: Path = Path(destination).resolve()

        if not src.exists():
            logger.error("move_file(): source does not exist: %s", src)
            return False

        try:
            shutil.move(str(src), str(dst))
            logger.info("Moved: %s -> %s", src, dst)
            return True

        except PermissionError:
            logger.error("Permission denied moving '%s' to '%s'.", src, dst)
            return False

        except OSError as exc:
            logger.error("Failed to move '%s' to '%s': %s", src, dst, exc)
            return False

    def organize_downloads(self) -> dict[str, int]:
        """
        Sort files in the Downloads folder into category subfolders.

        Files are categorised by their extension using the
        ``FILE_CATEGORIES`` mapping from ``config.settings``.
        Unknown extensions are placed into an ``"Other"`` folder.

        Sub-directories already present in Downloads are skipped.

        Returns
        -------
        dict[str, int]
            A summary mapping each category name to the number of
            files that were moved into it.
            Example: ``{"Documents": 5, "Images": 12, "Other": 3}``

        Examples
        --------
        >>> FileManager().organize_downloads()
        {'Documents': 3, 'Images': 7, 'Archives': 1}
        """
        downloads: Path = Path(DOWNLOADS_DIR).resolve()

        # Guard: does the Downloads folder exist?
        if not downloads.exists():
            logger.error("Downloads directory does not exist: %s", downloads)
            return {}

        if not downloads.is_dir():
            logger.error("Downloads path is not a directory: %s", downloads)
            return {}

        # Counters -- {category_name: files_moved}
        summary: dict[str, int] = {}

        logger.info("Organising downloads in: %s", downloads)

        # Iterate only *files* in the top level of Downloads.
        # ``iterdir()`` yields both files and directories, so we
        # filter with ``is_file()``.
        for item in downloads.iterdir():
            # Skip subdirectories (we only sort loose files).
            if not item.is_file():
                continue

            # Determine the target category from the file extension.
            extension: str = item.suffix.lower()  # e.g. ".PDF" -> ".pdf"
            category: str = get_category_for_extension(extension)

            # Create the category subfolder if it doesn't exist yet.
            category_folder: Path = downloads / category
            category_folder.mkdir(parents=True, exist_ok=True)

            # Build the destination path.
            dest: Path = category_folder / item.name

            # Handle filename collisions by appending a counter.
            # e.g. "report.pdf" -> "report_1.pdf" -> "report_2.pdf"
            counter: int = 1
            while dest.exists():
                dest = category_folder / f"{item.stem}_{counter}{item.suffix}"
                counter += 1

            try:
                shutil.move(str(item), str(dest))
                summary[category] = summary.get(category, 0) + 1
                logger.debug("Moved '%s' -> '%s'", item.name, dest)

            except OSError as exc:
                logger.error("Failed to move '%s': %s", item.name, exc)

        logger.info(
            "Downloads organised. Summary: %s",
            summary if summary else "(no files to organise)",
        )
        return summary

    def list_files(self, path: str) -> list[str]:
        """
        List all files (not subdirectories) in a directory.

        Parameters
        ----------
        path : str
            Path to the directory to list.

        Returns
        -------
        list[str]
            Sorted list of filenames (basenames, not full paths).
            Returns an empty list if the path is invalid or empty.

        Examples
        --------
        >>> FileManager().list_files("C:/Users/sk600/Documents")
        ['notes.txt', 'report.pdf', 'todo.md']
        """
        if not path or not path.strip():
            logger.error("list_files() called with an empty path.")
            return []

        target: Path = Path(path).resolve()

        if not target.exists():
            logger.error("list_files(): path does not exist: %s", target)
            return []

        if not target.is_dir():
            logger.error("list_files(): path is not a directory: %s", target)
            return []

        try:
            files: list[str] = sorted(
                item.name for item in target.iterdir() if item.is_file()
            )
            logger.info("Listed %d files in: %s", len(files), target)
            return files

        except PermissionError:
            logger.error("Permission denied listing directory: %s", target)
            return []

        except OSError as exc:
            logger.error("Failed to list directory '%s': %s", target, exc)
            return []
