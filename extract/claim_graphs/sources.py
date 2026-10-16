"""Where a document comes from — resolving a reference to a local file.

`prepare.py` slices a document into the agent inputs and knows nothing about publishers. This
module is the seam: a Source turns a reference (a DOI, a URL, a path) into a cached local file
and says what format it is in. eLife lives here and nowhere else, which is what lets the
machinery be published without the corpus (docs/design/2026-09-13-the-split.md § 4).

A source is registered in `BUILT_IN` or discovered through the `claim_graphs.sources` entry
point group, so an adapter for another publisher ships in its own package. The target is the
class, in the distribution that ships it — the example is hypothetical on purpose, because the
built-ins are registered through `BUILT_IN` and would teach the mechanism wrong:

    [project.entry-points."claim_graphs.sources"]
    biorxiv = "claim_graphs_biorxiv.sources:BiorxivSource"

`Resolved.sha256` is not decoration. The pipeline decides staleness by hashing what a layer
read (`runs/<paper>/ledger.jsonl`), so a source that cached by URL alone — returning a stale
file under a live-looking name — would defeat it silently.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)

Format = Literal["jats", "pdf"]

SOURCE_ENTRY_POINT_GROUP = "claim_graphs.sources"


def graph_root() -> Path:
    """Where a relative local reference is resolved from: the graph, not the caller's cwd."""
    return Path(os.environ.get("CLAIM_GRAPHS_ROOT") or Path.cwd()).expanduser().resolve()


def local_path(ref: str) -> Path:
    """A reference to a file on disk, as an absolute path.

    Relative references resolve against the graph root rather than the working directory, and
    that is the whole point of this function. A paper's reference is written once in its
    `index.md` and then copied verbatim into every claim file's `assertions:` block, so an
    absolute path there writes one machine's home directory into every file of a corpus — 87
    of them, in the run that found this. It also could not be anything else before now: the
    commands run from `extract/` and from the repository root, so a relative path meant two
    different files depending on which one invoked it, and only an absolute path worked.
    """
    p = Path(str(ref)).expanduser()
    return p if p.is_absolute() else (graph_root() / p)

# Kept at the historical path: moving it would silently re-download every cached paper. The
# rename belongs with the package rename (§ 7 step 4), not here.
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "claim-graphs"


@dataclass(frozen=True)
class Resolved:
    """A document located on disk, with enough provenance to reproduce the fetch."""

    path: Path
    format: Format
    ref: str
    source: str
    url: str | None = None
    doc_id: str | None = None          # the publisher's own id, where it has one
    sha256: str = ""
    # Set only when the file `path` points at was produced from `ref` rather than being it —
    # a conversion. Left None by every source that returns the document it was given, so
    # their `note` is unchanged to the byte and no existing corpus is marked stale.
    via: str | None = None

    # The exact wording matters: it is written into runs/<paper>/prepared.json, the ledger
    # hashes that file, and a cosmetic change would mark every paper stale.
    FORMAT_LABEL = {"jats": "JATS-XML", "pdf": "PDF"}

    @property
    def note(self) -> str:
        """One line for `PreparedPaper.extraction_path_note`."""
        where = self.url or f"local file at {self.path}"
        label = self.FORMAT_LABEL.get(self.format, self.format.upper())
        return f"{label} from {where}" + (f", converted by {self.via}" if self.via else "")


@runtime_checkable
class Source(Protocol):
    """Resolves a document reference to a local file a reader layer can parse."""

    name: str

    def handles(self, ref: str) -> bool:
        """True if this source can resolve `ref`."""

    def resolve(self, ref: str, cache_dir: Path | None = None,
                prefer: Format | None = None) -> Resolved:
        """Retrieve `ref`, caching under `cache_dir`. `prefer` picks among formats it offers."""


def _cached_fetch(url: str, cached: Path, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    if cached.is_file() and cached.stat().st_size > 0:
        logger.info("using cached %s", cached)
        return cached
    logger.info("fetching %s", url)
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        cached.write_bytes(resp.content)
    return cached


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ElifeSource:
    """eLife: a DOI of the form 10.7554/eLife.<id>, served from the eLife CDN.

    JATS is preferred because every eLife article has it, and it carries labelled sections,
    typed figures and structured references that the PDF heuristics can only guess at.
    """

    name = "elife"
    formats: tuple[Format, ...] = ("jats", "pdf")

    PDF_URL = "https://cdn.elifesciences.org/articles/{doc_id}/elife-{doc_id}-v1.pdf"
    XML_URL = "https://cdn.elifesciences.org/articles/{doc_id}/elife-{doc_id}-v1.xml"
    DOI_RE = re.compile(r"10\.7554/eLife\.(\d+)", re.IGNORECASE)

    def handles(self, ref: str) -> bool:
        return bool(self.DOI_RE.match(str(ref).strip()))

    def doc_id(self, ref: str) -> str:
        m = self.DOI_RE.match(str(ref).strip())
        if not m:
            raise ValueError(
                f"Not a recognized eLife DOI: {ref!r}. Expected 10.7554/eLife.<article-id>"
            )
        return m.group(1)

    def resolve(self, ref: str, cache_dir: Path | None = None,
                prefer: Format | None = None) -> Resolved:
        fmt: Format = prefer or "jats"
        if fmt not in self.formats:
            raise ValueError(f"{self.name} does not serve {fmt!r}")
        doc_id = self.doc_id(ref)
        cache_dir = cache_dir or DEFAULT_CACHE_DIR
        url = (self.XML_URL if fmt == "jats" else self.PDF_URL).format(doc_id=doc_id)
        suffix = "xml" if fmt == "jats" else "pdf"
        path = _cached_fetch(url, cache_dir / f"elife-{doc_id}-v1.{suffix}", cache_dir)
        return Resolved(path=path, format=fmt, ref=ref, source=self.name, url=url,
                        doc_id=doc_id, sha256=sha256_of(path))


class FileSource:
    """A document already on disk. The fallback that makes the package usable with no network."""

    name = "file"
    SUFFIX_FORMAT: dict[str, Format] = {".pdf": "pdf", ".xml": "jats", ".nxml": "jats"}

    def handles(self, ref: str) -> bool:
        p = local_path(ref)
        return p.suffix.lower() in self.SUFFIX_FORMAT and p.is_file()

    def resolve(self, ref: str, cache_dir: Path | None = None,
                prefer: Format | None = None) -> Resolved:
        path = local_path(ref).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        fmt = self.SUFFIX_FORMAT.get(path.suffix.lower())
        if fmt is None:
            raise ValueError(f"cannot tell the format of {path.name} from its suffix")
        if prefer and prefer != fmt:
            raise ValueError(f"{path.name} is {fmt}, not {prefer}")
        return Resolved(path=path, format=fmt, ref=str(ref), source=self.name,
                        doc_id=None, sha256=sha256_of(path))


class PandocSource:
    """A manuscript in a format pandoc reads, converted to JATS on the way in.

    `prepare()` has two branches and they are not equal. JATS goes to `parse_jats`, which reads
    labelled structure — abstract, sections by their titles, captions bound to figure ids,
    tables with their rows. Everything else falls to flat text and regex. So the useful question
    for a new format is not "can we parse it" but "how does it reach the structured branch",
    and for every format pandoc reads the answer is: pandoc already writes JATS.

    That buys Markdown, Word, LaTeX, HTML and OpenDocument for the cost of a subprocess, and
    none of them needs a parser here. PDF is not among them — pandoc does not read PDF — which
    is why the flat-text path still exists and is still the lossy one.

    WHAT SURVIVES DIFFERS BY FORMAT, and the difference is metadata, not prose. Body sections
    come through from all of them: results and methods slice the same from .md, .docx, .html
    and .tex. Title and abstract come through only where the source format records them as
    metadata rather than as a heading — Markdown with YAML front matter carrying `title:` and
    `abstract:` is the case that keeps everything, .docx keeps the title, and .html and .tex
    arrive with neither. An `# Abstract` heading is a section like any other and does not
    become `<abstract>`, so a document written that way prepares with an empty abstract slice
    and no error. Prefer Markdown with front matter where there is a choice.
    """

    name = "pandoc"

    # Deliberately not .xml/.nxml/.pdf: FileSource claims those, is registered ahead of this
    # one, and round-tripping JATS through pandoc would lose structure it already has.
    SUFFIXES = frozenset({".md", ".markdown", ".docx", ".tex", ".latex",
                          ".html", ".htm", ".odt", ".rst", ".epub"})

    # pandoc's reader is usually its own name for the suffix; where it is not, say so.
    READER = {".md": "markdown", ".markdown": "markdown", ".tex": "latex", ".latex": "latex",
              ".htm": "html"}

    def handles(self, ref: str) -> bool:
        p = local_path(ref)
        return p.suffix.lower() in self.SUFFIXES and p.is_file()

    @staticmethod
    def _pandoc() -> str:
        """The pandoc binary, or a refusal that names it.

        A source that quietly declined here would leave `for_ref` reporting "no source handles
        this reference", which sends the reader to look for a missing adapter rather than a
        missing program.
        """
        exe = shutil.which("pandoc")
        if exe is None:
            raise RuntimeError(
                "pandoc is not installed, and it is what converts this format to JATS. "
                "Install it (https://pandoc.org/installing.html), or pass JATS XML directly."
            )
        return exe

    @classmethod
    def _version(cls, exe: str) -> str:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
        return (out.stdout.splitlines() or ["pandoc"])[0].strip()

    def resolve(self, ref: str, cache_dir: Path | None = None,
                prefer: Format | None = None) -> Resolved:
        path = local_path(ref).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        if prefer and prefer != "jats":
            raise ValueError(f"{path.name} can only be offered as jats, not {prefer}")

        exe = self._pandoc()
        digest = sha256_of(path)
        cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR) / "pandoc"
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Named by the source's own hash, so editing the manuscript converts again and leaving
        # it alone does not.
        out = cache_dir / f"{path.stem}-{digest[:16]}.jats.xml"

        if not (out.is_file() and out.stat().st_size > 0):
            reader = self.READER.get(path.suffix.lower(), path.suffix.lower().lstrip("."))
            logger.info("converting %s to JATS with pandoc", path.name)
            # --wrap=none: pandoc otherwise wraps long lines, and a wrap inside <article-title>
            # puts a newline in the middle of the paper's title.
            proc = subprocess.run(
                [exe, str(path), "-f", reader, "-t", "jats", "-s", "--wrap=none",
                 "-o", str(out)],
                capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                out.unlink(missing_ok=True)
                raise RuntimeError(
                    f"pandoc could not convert {path.name} to JATS "
                    f"(exit {proc.returncode}): {proc.stderr.strip()[:400]}")

        # The hash is of the manuscript, not of the conversion. Staleness asks whether the
        # input changed; hashing pandoc's output would make every ledger record depend on the
        # pandoc version instead, and re-running after an upgrade would mark papers stale for a
        # reason that has nothing to do with them. The version goes in the note, where a reader
        # can see it without it being load-bearing.
        return Resolved(path=out, format="jats", ref=str(ref), source=self.name,
                        doc_id=None, sha256=digest, via=self._version(exe))


BUILT_IN: tuple[type, ...] = (ElifeSource, FileSource, PandocSource)


def registry() -> list[Source]:
    """Built-in sources first, then any registered through the entry point group.

    Built-ins come first so a plugin cannot silently shadow eLife handling; a plugin claiming a
    reference no built-in handles is the supported case.
    """
    sources: list[Source] = [cls() for cls in BUILT_IN]
    try:
        from importlib.metadata import entry_points
        for ep in entry_points(group=SOURCE_ENTRY_POINT_GROUP):
            try:
                sources.append(ep.load()())
            except Exception:                                   # noqa: BLE001
                logger.warning("source plugin %r failed to load", ep.name, exc_info=True)
    except Exception:                                           # noqa: BLE001
        logger.debug("entry-point discovery unavailable", exc_info=True)
    return sources


def for_ref(ref: str) -> Source:
    """The first source that handles `ref`."""
    for source in registry():
        if source.handles(ref):
            return source
    raise ValueError(
        f"no source handles {ref!r}. Built-in sources: "
        f"{', '.join(cls.name for cls in BUILT_IN)}. "
        f"Pass a DOI, a local PDF or JATS XML path, a manuscript in a format pandoc reads "
        f"({', '.join(sorted(PandocSource.SUFFIXES))}), or register a source in the "
        f"{SOURCE_ENTRY_POINT_GROUP!r} entry point group."
    )


def resolve(ref: str, cache_dir: Path | None = None, prefer: Format | None = None) -> Resolved:
    return for_ref(ref).resolve(ref, cache_dir=cache_dir, prefer=prefer)
